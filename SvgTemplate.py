import base64
from collections import OrderedDict
import copy
import os
import re
import xml.etree.ElementTree as ET

import Code128

from io import BytesIO

"""Exception class for invalid template specifications"""
class SvgTemplateException(Exception):
  pass

"""Removes the namespace from a XML tag"""
def strip_tag(tag):
  if "}" in tag:
    return tag.split('}', 1)[1]
  else:
    return tag

"""Returns all the text from a text element, ignoring formatting
(in particular, line breaks may be ignored)"""
def get_text_contents(elt):
  contents = []

  def process_child(child_elt):
    if strip_tag(child_elt.tag) in ['text', 'tspan']:
      if child_elt.text:
        contents.append(child_elt.text)
      for child_child_elt in child_elt:
        process_child(child_child_elt)
    elif strip_tag(child_elt.tag) in ['altGlyph', 'altGlyphDef', 'altGlyphItem', 'glyph', 'glyphRef', 'textPath', 'tref']:
      raise NotImplementedError("get_text_contents only supports tspan children, got '%s'" % strip_tag(child_elt.tag))
    else:
      # discard non-text elements
      pass

  process_child(elt)
  return "".join(contents)

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

class TemplateFilter:
  """Apply this filter on a elemement. Called once for each element in the
  SVG tree in preorder traversal. May mutate both the element and its children.
  """
  def apply(self, template, elt, data_dict):
    raise NotImplementedError()

"""A class that does text replacement on text and tspan content using Python
style string interpolation"""
class TextFilter(TemplateFilter):
  def apply(self, template, elt, data_dict):
    if strip_tag(elt.tag) in ['text', 'tspan', 'flowRoot', 'flowPara', 'flowSpan'] and elt.text:
      def parsed(match):
        key = match.group(1)
        # TODO: more robust error handling
        assert key in data_dict, "missing key %s" % key
        return data_dict[key]
      elt.text = re.sub(r"%\(([^(^)]+)\)", parsed, elt.text)

"""Replaces a group which consists of only a textbox (image replacement command)
and rectangle (image sizing) with an image
The rectangle is replaced with the image, and the text element is removed (this
preserves any transforms within the group)."""
class AreaFilter(TemplateFilter):
  """Perform substitution given the text and rectangle element
  Can return either a list of SVG elements to insert into the group, or None to
  leave things as-is (if the command isn't applicable).

  TODO: better API that isn't guess and check.
  """
  def replace(self, template, command_text, rect_elt):
    raise NotImplementedError()

  def apply(self, template, elt, data_dict):
    # Check if is a group, and if so, if only two elements are a text and rect
    if strip_tag(elt.tag) != 'g' or len(elt) != 2:
      return
    if (strip_tag(elt[0].tag) == 'rect' and strip_tag(elt[1].tag) == 'text'):
      rect_elt = elt[0]
      text_elt = elt[1]
    elif (strip_tag(elt[0].tag) == 'text' and strip_tag(elt[1].tag) == 'rect'):
      rect_elt = elt[1]
      text_elt = elt[0]
    else:
      return

    new_elts = self.replace(template, get_text_contents(text_elt), rect_elt)
    if new_elts is not None:
      elt.remove(rect_elt)
      elt.remove(text_elt)
      for new_elt in new_elts:
        elt.insert(len(elt), new_elt)

def elt_attrs_to_dict(elt, attrs):
  out_dict = {}
  for attr in attrs:
    val = elt.get(attr, None)
    if val is not None:
      out_dict[attr] = val
  return out_dict

class CommandSyntaxError(Exception):
  pass

"""
Command parser, parses a standardized command string (#cmd (kwarg=kwval) vals),
verifying that the command matches and providing the positional and keyword
arguments. Also ensures that all the positional and keyword arguments are used.
"""
class Command:
  def __init__(self, cmd_str):
    self.cmd_str = cmd_str
    cmd_split = [elt for elt in cmd_str.split(' ') if elt]
    cmd = cmd_split[0]
    if not cmd.startswith('#'):
      raise CommandSyntaxError("Command '%s' first element '%s' didn't start with '#'" % (cmd_str, cmd))
    self.cmd = cmd[1:]  # discard the '#'
    cmd_args = cmd_split[1:]
    self.kw_args = {}
    self.pos_args = []
    for cmd_arg in cmd_args:
      if '=' in cmd_arg:
        arg_split = cmd_arg.split('=')
        if len(arg_split) != 2:
          raise CommandSyntaxError("Command '%s' keyword arg '%s' must have exactly one '='" % (cmd_str, cmd_arg))
        if arg_split[0] in self.kw_args:
          raise CommandSyntaxError("Command '%s' redefined keyword arg '%s'" % (cmd_str, arg_split[0]))
        self.kw_args[arg_split[0]] = arg_split[1]
      else:
        self.pos_args.append(cmd_arg)

    self.kw_args_accessed = set()
    self.pos_args_accessed = set()

  def get_num_pos_args(self):
    return len(self.pos_args)

  def get_pos_arg(self, index, desc):
    if index >= len(self.pos_args):
      raise CommandSyntaxError("Command '%s' missing arg %i (%s)" % (self.cmd_str, index, desc))
    self.pos_args_accessed.add(index)
    return self.pos_args[index]

  def get_kw_keys(self):
    return self.kw_args.keys()

  def get_kw_arg(self, kw, desc, default=CommandSyntaxError):
    if kw not in self.kw_args:
      if default == CommandSyntaxError:
        raise CommandSyntaxError("Command '%s' missing required keyword arg %s (%s)" % (self.cmd_str, kw, desc))
      else:
        return default
    self.kw_args_accessed.add(kw)
    return self.kw_args[kw]

  def finalize(self):
    pos_args_unaccessed = set(range(len(self.pos_args))) - self.pos_args_accessed
    if pos_args_unaccessed:
      raise CommandSyntaxError("Command '%s' has unused positional arguments %s" % (self.cmd_str, pos_args_unaccessed))

    kw_args_unaccessed = set(self.kw_args.keys()) - self.kw_args_accessed
    if kw_args_unaccessed:
      raise CommandSyntaxError("Command '%s' has unused keyword arguments %s" % (self.cmd_str, kw_args_unaccessed))

"""Deletes the contents of a group if conditions are not met."""
class ShowFilter(TemplateFilter):
  def apply(self, template, elt, data_dict):
    # Check if is a group, and if so, if only two elements are a text and rect
    if strip_tag(elt.tag) != 'g':
      return

    cmd_text = None
    cmd_elt = None
    for subelt in elt:
      if strip_tag(subelt.tag) == 'text' and get_text_contents(subelt).startswith('#showeq'):
        assert cmd_text is None, "Found multiple #show command in same group"
        cmd_text = get_text_contents(subelt)
        cmd_elt = subelt

    if cmd_text is None:
      return

    elt.remove(cmd_elt)
    cmd = Command(cmd_text)

    str_check = cmd.get_pos_arg(0, "item to check")
    str_in = [cmd.get_pos_arg(i, "allowed value") for i in range(1, cmd.get_num_pos_args())]

    if str_check not in str_in:
      elt.clear()

"""
Takes in a command and a rect elt in a group and generates a code128 barcode
image (sized to the rect) which is then embedded into the SVG.
"""
class BarcodeFilter(AreaFilter):
  def replace(self, template, command_text, rect_elt):
    if not command_text.startswith('#code128'):
      return None
    cmd = Command(command_text)

    # empty request generates nothing
    if cmd.get_num_pos_args() == 0:
      return []

    x = units_to_pixels(rect_elt.get('x'))
    width = units_to_pixels(rect_elt.get('width'))

    y_str = rect_elt.get('y')
    height_str = rect_elt.get('height')

    alignment = cmd.get_kw_arg('align', 'alignment', 'xMid')
    fill = cmd.get_kw_arg('fill', 'fill color', '#000000')
    quiet = cmd.get_kw_arg('quiet', 'add quiet zone', default='True')
    if quiet in ['true', 'True']:
      quiet = True
    elif quiet in ['False', 'false']:
      quiet = False
    else:
      raise CommandSyntaxError("quiet='%s' not a bool" % quiet)
    thickness = units_to_pixels(cmd.get_kw_arg('thickness', 'barcode thickness', 3))
    val = cmd.get_pos_arg(0, 'barcode value')
    cmd.finalize()

    barcode_widths = Code128.code128_widths(val)
    barcode_widths = [x * thickness for x in barcode_widths]
    barcode_width = sum(barcode_widths)

    if quiet:
      barcode_width += 20 * thickness
    if barcode_width > width:
      raise SvgTemplateException("Barcode '%s' with width %s exceeds allocated width %s" % (val, barcode_width, width))

    if alignment == 'xMin':
      curr_x = x
    elif alignment == 'xMid':
      curr_x = x + ((width - barcode_width) / 2)
    elif alignment == 'xMax':
      curr_x = x + width - barcode_width

    if quiet:
      curr_x += 10 * thickness

    assert len(barcode_widths) % 2 == 1

    output_elts = []
    draw_bar = True
    for bar_width in barcode_widths:
      if draw_bar:
        output_elts.append(ET.Element('rect', {
          'x': str(curr_x),
          'y': y_str,
          'width': str(bar_width),
          'height': height_str,
          'style': 'stroke:none;fill:%s;fill-opacity:1' % (fill),
        }))
      curr_x += bar_width
      draw_bar = not draw_bar

    return output_elts

"""
Takes in a command and a rect (may be less restricted in the future) in a group
and changes the style attribute based. Each keyword argument in the command
becomes a style key/value, overwriting existing ones. Order of style elements
in the SVG is preserved.
"""
class StyleFilter(AreaFilter):
  def replace(self, template, command_text, rect_elt):
    if not command_text.startswith('#style'):
      return None
    cmd = Command(command_text)

    style_dict = OrderedDict()
    for style_kv in rect_elt.get('style', '').split(';'):
      kv = style_kv.split(':')
      assert len(kv) == 2
      if kv[0] in style_dict:
        raise SvgTemplateException("Duplicate style key '%s' in template" % kv[0])
      style_dict[kv[0]] = kv[1]

    for kwkey in cmd.get_kw_keys():
      style_dict[kwkey] = cmd.get_kw_arg(kwkey, "(style key-argument pair)")

    style_elts = ['%s:%s' % (k, v) for k, v in style_dict.items()]
    rect_elt.set('style', ';'.join(style_elts))

    return [rect_elt]

"""
Takes in a command and a rect (may be less restricted in the future) in a group
and includes sub-SVG files. Templating is not done on the included SVG files.
By default, centers the included SVG (by viewport) without scaling.
In the future, will clip the included SVG to the rectangular area.
"""
class SvgFilter(AreaFilter):
  def replace(self, template, command_text, rect_elt):
    if not command_text.startswith('#svg'):
      return None
    cmd = Command(command_text)

    outputs = []

    attrs = elt_attrs_to_dict(rect_elt, ['x', 'y', 'height', 'width'])
    rect_center_x = units_to_pixels(rect_elt.get('x')) + (units_to_pixels(rect_elt.get('width')) / 2)
    rect_center_y = units_to_pixels(rect_elt.get('y')) + (units_to_pixels(rect_elt.get('height')) / 2)

    template_dir = template.get_template_directory()

    for i in range(cmd.get_num_pos_args()):
      sub_etree = ET.parse(os.path.join(template_dir, cmd.get_pos_arg(i, "SVG file to include"))).getroot()
      sub_width = units_to_pixels(sub_etree.get('width'))
      sub_height = units_to_pixels(sub_etree.get('height'))
      sub_viewbox = sub_etree.get('viewBox').split(' ')
      sub_viewbox = [float(elt) for elt in sub_viewbox]
      assert sub_viewbox[0] == 0, "TODO: support viewbox with origin != 0"
      assert sub_viewbox[1] == 0, "TODO: support viewbox with origin != 0"
      assert abs(sub_viewbox[2] - sub_width) < 0.1, "TODO: support viewbox width != svg width"
      assert abs(sub_viewbox[3] - sub_height) < 0.1, "TODO: support viewbox height != svg height"

      delta_x = rect_center_x - (sub_width / 2)
      delta_y = rect_center_y - (sub_height / 2)

      new_group = ET.Element('{http://www.w3.org/2000/svg}g',
                             attrib={"transform": "translate(%f ,%f)" % (delta_x, delta_y)})
      for elt in sub_etree:
        new_group.append(elt)

      outputs.append(new_group)

    return outputs

class TemplateError(Exception):
  pass

class SvgTemplate:
  # a whitelist of SVG XML tags to treat as the template part
  SVG_ELEMENTS = ["g"]

  """Initialize a template from a SVG etree and list of filters to apply
  Note: filter order matters, filters are run sequentially through the tree
  (each filter is run through the whole tree before the next filter runs).
  """
  def __init__(self, template_filename, filters):
    self.template_filename = template_filename
    self.base_etree = ET.parse(template_filename)
    self.filters = filters

    # Split etree between base and template
    self.template_elts = []
    for child_elt in self.base_etree.getroot():
      if strip_tag(child_elt.tag) in self.SVG_ELEMENTS:
        self.template_elts.append(child_elt)
    for template_elt in self.template_elts:
      self.base_etree.getroot().remove(template_elt)

  """Returns the non-template portion of the input SVG etree."""
  def clone_base(self):
    return copy.deepcopy(self.base_etree)

  """Returns the list of filters for this template."""
  def get_filters_list(self):
    return self.filters

  def get_template_directory(self):
    return os.path.dirname(self.template_filename)

  """Instantiate the template on a input set of data (a dict of keys to values),
  returning a list of SVG etree nodes."""
  def generate(self, data_dict):
    def substitute(filter_obj, elt):
      filter_obj.apply(self, elt, data_dict)
      for child in elt:
        substitute(filter_obj, child)

    elts = copy.deepcopy(self.template_elts)
    for filter_obj in self.filters:
      for elt in elts:
        substitute(filter_obj, elt)

    return elts
