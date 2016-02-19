import argparse
import csv
import codecs
import xml.etree.ElementTree as ET
import re

from SvgTemplate import SvgTemplate, TextFilter, BarcodeFilter

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

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="Generate label sheet from SVG template")
  parser.add_argument('template', type=str,
                      help="SVG label template")
  parser.add_argument('data', type=str,
                      help="CSV data")
  parser.add_argument('output', type=str,
                      help="SVG generated labels output")
  args = parser.parse_args()
  
  ET.register_namespace('', "http://www.w3.org/2000/svg")
  template_etree = ET.parse(args.template)
  data_reader = csv.DictReader(codecs.open(args.data, encoding='utf-8'))

  template = SvgTemplate(template_etree, [TextFilter(),
                                          BarcodeFilter()])
  output = template.get_base()
  
  num_rows = int(template.get_config('nrows'))
  num_cols = int(template.get_config('ncols'))
  curr_row = 0
  curr_col = 0
  
  for row in data_reader:
    # TODO: make namespace parsing & handling general
    incx = units_to_pixels(template.get_config("incx")) * curr_col
    incy = units_to_pixels(template.get_config("incy")) * curr_row
    new_group = ET.SubElement(output.getroot(), "{http://www.w3.org/2000/svg}g",
                              attrib={"transform": "translate(%f ,%f)" % (incx, incy)})
    
    for elt in template.generate(row):
      new_group.append(elt)
    
    curr_row += 1
    if curr_row == num_rows:
      curr_row = 0
      curr_col += 1
    if curr_col == num_cols:
      assert False, "TODO: handle col overflow, newpage support"
      
  output.write(args.output)