import argparse
import csv
import codecs
import configparser
import xml.etree.ElementTree as ET
import re
import sys
reload(sys)
sys.setdefaultencoding('UTF8')


from SvgTemplate import SvgTemplate, TextFilter, BarcodeFilter, StyleFilter

# TODO: deduplicate with SvgTemplate, also generally more elegant handling of
# namespaces
"""Removes the namespace from a XML tag"""
def strip_tag(tag):
  if "}" in tag:
    return tag.split('}', 1)[1]
  else:
    return tag

class LabelmakerInputException(Exception):
  pass

# from http://www.w3.org/TR/SVG/coords.html#Units
UNITS_TO_PX = {
  "pt": 1.25,
  "pc": 15,
  "mm": 3.543307,
  "cm": 35.43307,
  "in" : 90
  }
def units_to_pixels(units_num):
  match = re.search(r"(\d*.?\d+)\s*(\w*)", units_num)
  if not match:
    raise LabelmakerInputException("Caanot parse length '%s'" % units_num)

  num = float(match.group(1))
  units = match.group(2)
  if units:
    assert units in UNITS_TO_PX
    num *= UNITS_TO_PX[units]
  return num

def config_get(config, section, option, desc):
  val = config.get(section, option, fallback=None)
  if val is None:
    assert False, "Configuration not specified for %s.%s (%s)" % (section, option, desc)
  return val

if __name__ == '__main__':
  sys.setdefaultencoding('UTF8')
  parser = argparse.ArgumentParser(description="Generate label sheet from SVG template")
  parser.add_argument('template', type=str,
                      help="SVG label template")
  parser.add_argument('config', type=str,
                      help="label sheet configuration")
  parser.add_argument('data', type=str,
                      help="CSV data")
  parser.add_argument('output', type=str,
                      help="SVG generated labels output")
  parser.add_argument('--only', type=str, default=None,
                      help="only process rows which have this key nonempty")
  parser.add_argument('--start_row', type=int, default=0,
                      help="starting row, zero is topmost")
  parser.add_argument('--start_col', type=int, default=0,
                      help="starting column, zero is leftmost")
  parser.add_argument('--dir', type=str, default='col',
                      choices=['col', 'row'],
                      help="direction labels are incremented in")
  args = parser.parse_args()
  
  ET.register_namespace('', "http://www.w3.org/2000/svg")
  template_etree = ET.parse(args.template)
  data_reader = csv.DictReader(codecs.open(args.data, encoding='utf-8'))
  
  if args.only:
    if '=' in args.only:
      split = args.only.split('=')
      assert len(split) == 2
      only_parse_key = split[0]
      only_parse_val = split[1]
    else:
      only_parse_key = args.only
      only_parse_val = None
  else:
    only_parse_key = None

  config = configparser.ConfigParser()
  config.read(args.config)

  template = SvgTemplate(template_etree, [TextFilter(),
                                          BarcodeFilter(),
                                          StyleFilter()])
  
  # Get the filename without the SVG extension so the page number can be added
  if args.output[-4:].lower() == '.svg'.lower():
    output_name = args.output[:-4]
  else:
    output_name = args.output  
  
  num_rows = int(config_get(config, 'sheet', 'nrows', "number of rows (vertical elements)"))
  num_cols = int(config_get(config, 'sheet', 'ncols', "number of columns (horizontal elements)"))

  offx = units_to_pixels(config_get(config, 'sheet', 'offx', "initial horizontal offset"))
  offy = units_to_pixels(config_get(config, 'sheet', 'offy', "initial vertical offset"))

  incx = units_to_pixels(config_get(config, 'sheet', 'incx', "horizontal spacing"))
  incy = units_to_pixels(config_get(config, 'sheet', 'incy', "vertical spacing"))
  
  sheet_sizex = units_to_pixels(config_get(config, 'sheet', 'sizex', "sheet width"))
  sheet_sizey = units_to_pixels(config_get(config, 'sheet', 'sizey', "sheet height"))
    
  if args.dir == 'row':
    min_spacing = incx
    maj_spacing = incy
    min_max = num_cols
    maj_max = num_rows
    curr_min = args.start_col
    curr_maj = args.start_row
  elif args.dir == 'col':
    min_spacing = incy
    maj_spacing = incx
    min_max = num_rows
    maj_max = num_cols
    curr_min = args.start_row
    curr_maj = args.start_col
  else:
    assert False
  
  assert curr_min < min_max, "starting position exceeds bounds"
  assert curr_maj < maj_max, "starting position exceeds bounds"

  curr_page = 0
  output = None
  
  for row in data_reader:
    if only_parse_key:
      if ((only_parse_val is None and not row[only_parse_key]) or
          (only_parse_val is not None and row[only_parse_key] != only_parse_val)):
        continue
    
    if output == None:
      output = template.clone_base()
      
      svg_elt = output.getroot()
      assert strip_tag(svg_elt.tag) == 'svg'
      svg_elt.set('width', str(sheet_sizex))
      svg_elt.set('height', str(sheet_sizey))
      svg_elt.set('viewBox', '{0 0 %s %s}' % (sheet_sizex, sheet_sizey))
    
    if args.dir == 'row':
      pos_x = offx + curr_min * incx
      pos_y = offy + curr_maj * incy
    elif args.dir == 'col':
      pos_y = offy + curr_min * incy
      pos_x = offx + curr_maj * incx
    else:
      assert False

    # TODO: make namespace parsing & handling general
    new_group = ET.SubElement(output.getroot(), "{http://www.w3.org/2000/svg}g",
                              attrib={"transform": "translate(%f ,%f)" % (pos_x, pos_y)})
    
    for elt in template.generate(row):
      new_group.append(elt)
    
    curr_min += 1
    if curr_min == min_max:
      curr_min = 0
      curr_maj += 1
    if curr_maj == maj_max:
      output.write("%s_%i.svg" % (output_name, curr_page))
      
      curr_maj = 0
      curr_page += 1
      
      output = None
  
  if output is not None:
    output.write("%s_%i.svg" % (output_name, curr_page))
  
