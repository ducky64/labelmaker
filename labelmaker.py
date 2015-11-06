import argparse
import csv
import xml.etree.ElementTree as ET

from SvgTemplate import SvgTemplate, TextFilter

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="Generate label sheet from SVG template")
  parser.add_argument('template', type=str,
                      help="SVG label template")
  parser.add_argument('data', type=str,
                      help="CSV data")
  parser.add_argument('output', type=str,
                      help="SVG generated labels output")
  args = parser.parse_args()
  
  template_etree = ET.parse(args.template)
  data_reader = csv.DictReader(open(args.data))

  template = SvgTemplate(template_etree, [TextFilter()])
  output = template.get_base()
  
  for row in data_reader:
    # TODO: make namespace parsing & handling general
    new_group = ET.SubElement(output.getroot(), tag="{http://www.w3.org/2000/svg}g",
                              attrib={"transform": "translate(10,10)"})
    for elt in template.generate(row):
      new_group.append(elt)
    
  output.write(args.output)