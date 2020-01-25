import argparse
import csv
import codecs
import xml.etree.ElementTree as ET

import os
import subprocess
import time

import win32api
import win32print

from SvgTemplate import SvgTemplate, TextFilter, ShowFilter, BarcodeFilter, StyleFilter, SvgFilter
from SvgTemplate import strip_tag

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="Prints labels from changed rows in a .csv file")

  parser.add_argument('template', type=str,
                      help="SVG label template")
  parser.add_argument('data', type=str,
                      help="CSV data")
  parser.add_argument('output', type=str,
                      help="SVG generated temporary prefix")
  parser.add_argument('--printer', type=str,
                      help="printer name, leave blank to only generate PDFs", default=None)
  parser.add_argument('--only', type=str, default=None,
                      help="only process rows which have this key nonempty")
  parser.add_argument('--data_fresh', action='store_true',
                      help="ignore the initial state of data (print all rows)")
  args = parser.parse_args()

  ET.register_namespace('', "http://www.w3.org/2000/svg")

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

  # TODO: deduplicate standard filter transforms w/ labelmaker
  template = SvgTemplate(args.template, [
    TextFilter(),
    ShowFilter(),
    BarcodeFilter(),
    StyleFilter(),
    SvgFilter(),
  ])

  # Get the filename without the SVG extension so the page number can be added
  if args.output[-4:].lower() == '.svg'.lower():
    output_name = args.output[:-4]
  else:
    output_name = args.output

  def canonicalize_row_dict(row_dict):
    return tuple(sorted([(k, v) for (k, v) in row_dict.items() if v]))

  def traverse(file_name, row_dict_fn):
    data_file = codecs.open(file_name, encoding='utf-8')
    data_reader = csv.DictReader(data_file)
    seen_set = set()
    for row_dict in data_reader:
      seen_set.add(canonicalize_row_dict(row_dict))
      row_dict_fn(row_dict)
    data_file.close()
    return seen_set

  def print_fn(seen_set):
    def actual_fn(row_dict):
      if (only_parse_key and
          ((only_parse_val is None and not row[only_parse_key]) or
           (only_parse_val is not None and row[only_parse_key] != only_parse_val))):
        return
      canonical_row_dict = canonicalize_row_dict(row_dict)
      if canonical_row_dict in seen_set:
        return
      print(canonical_row_dict)

      output = template.clone_base()
      svg_elt = output.getroot()
      assert strip_tag(svg_elt.tag) == 'svg'
      for elt in template.generate(row_dict):
        svg_elt.append(elt)

      output.write(output_name + ".svg")

      subprocess.Popen([
        'inkscape', '--without-gui', output_name + '.svg' ,
        '--export-pdf=' + output_name + '.pdf'
      ]).communicate()

      if args.printer is not None:
        win32api.ShellExecute(0,
          "print", output_name + '.pdf',
          '/d:"%s"' % args.printer, ".", 0)
    return actual_fn

  # Read in the current rows and ignore those
  
  if args.data_fresh:
    last_mod_time = None
    seen_set = set()
  else:
    last_mod_time = os.path.getmtime(args.data)
    seen_set = traverse(args.data, lambda x: x)
  print(f"Ready, ignored initial {len(seen_set)} rows")

  while True:
    if os.path.isfile(args.data):
      mod_time = os.path.getmtime(args.data)

      if last_mod_time is None or mod_time != last_mod_time:
        print("File modification detected")
        seen_set = traverse(args.data, print_fn(seen_set))
        print("Done")

      last_mod_time = mod_time
    else:
      print("Warning: file not found")
      
    time.sleep(0.25)
