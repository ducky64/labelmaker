import argparse
import csv
import xml.etree.ElementTree as ET

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="Generate label sheet from SVG template")
  parser.add_argument('template', type=str,
                      help="SVG label template")
  parser.add_argument('data', type=str,
                      help="CSV data")
  args = parser.parse_args()
  
  template = ET.parse(args.template).getroot()
  data_reader = csv.DictReader(open(args.data))
