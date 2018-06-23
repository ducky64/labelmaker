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
  parser = argparse.ArgumentParser(description="Print labels from .csv files")

  parser.add_argument('template', type=str,
                      help="SVG label template")
  parser.add_argument('data', type=str,
                      help="CSV data")
  parser.add_argument('printed', type=str,
                      help="CSV of printed columns")
  parser.add_argument('output', type=str,
                      help="SVG generated temporary prefix")
  parser.add_argument('printer', type=str,
                      help="printer name")
  parser.add_argument('--only', type=str, default=None,
                      help="only process rows which have this key nonempty")
  args = parser.parse_args()

  ET.register_namespace('', "http://www.w3.org/2000/svg")
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


  for (i, row) in enumerate(data_reader):
    if only_parse_key:
      if ((only_parse_val is None and not row[only_parse_key]) or
          (only_parse_val is not None and row[only_parse_key] != only_parse_val)):
        continue

    print(row)

    output = template.clone_base()
    svg_elt = output.getroot()
    assert strip_tag(svg_elt.tag) == 'svg'
    for elt in template.generate(row):
      svg_elt.append(elt)

    output.write(output_name + ".svg")

    subprocess.Popen([
      'inkscape', '--without-gui', output_name + '.svg' ,
      '--export-pdf=' + output_name + '.pdf'
    ]).communicate()

    win32api.ShellExecute(0,
      "print", output_name + '.pdf',
      '/d:"%s"' % args.printer, ".", 0)
