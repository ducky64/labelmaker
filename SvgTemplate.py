import base64
from collections import OrderedDict
import copy
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
    if strip_tag(child_elt.tag) not in ['text', 'tspan']:
      raise NotImplementedError("get_text_contents only supports tspan children, got '%s'" % strip_tag(child_elt.tag))
    if child_elt.text:
      contents.append(child_elt.text)
    for child_child_elt in child_elt:
      process_child(child_child_elt)
  process_child(elt)
  return "".join(contents)

class TemplateFilter:
  """Apply this filter on a elemement. Called once for each element in the
  SVG tree in preorder traversal. May mutate both the element and its children.
  """ 
  def apply(self, elt, data_dict):
    raise NotImplementedError()

"""A class that does text replacement on text and tspan content using Python
style string interpolation"""
class TextFilter(TemplateFilter):
  def apply(self, elt, data_dict):
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
class ImageFilter(TemplateFilter):
  """Perform image substitution given the text and rectangle element
  Can return either a list of SVG elements to insert into the group, or None to
  leave things as-is (for example, if the text command isn't valid.
  """
  def replace(self, text, rect_elt):
    raise NotImplementedError()
  
  def apply(self, elt, data_dict):
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
      
    new_elts = self.replace(get_text_contents(text_elt), rect_elt)
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

"""
Takes in a command and a rect elt in a group and generates a code128 barcode
image (sized to the rect) which is then embedded into the SVG.
"""
class BarcodeFilter(ImageFilter):
  def replace(self, text, rect_elt):
    if not text.startswith('#code128'):
      return
    cmd = Command(text)
    
    attrs = elt_attrs_to_dict(rect_elt, ['x', 'y', 'height', 'width'])
    attrs['preserveAspectRatio'] = cmd.get_kw_arg('align', 'rescale alignment', 'xMidYMid')
    quiet = cmd.get_kw_arg('quiet', 'add quiet zone', default='True')
    if quiet in ['true', 'True']:
      quiet = True
    elif quiet in ['False', 'false']:
      quiet = False
    else:
      raise CommandSyntaxError("quiet='%s' not a bool" % quiet)
    thickness = int(cmd.get_kw_arg('thickness', 'barcode thickness', 3))
    val = cmd.get_pos_arg(0, 'barcode value')
    cmd.finalize()
    
    image = Code128.code128_image(val, thickness=thickness, quiet_zone=quiet)
    image_output = BytesIO()
    image.save(image_output, format='PNG')
    image_base64 = base64.b64encode(image_output.getvalue())
    image_output.close()
    data_string = "data:image/png;base64," + image_base64.decode("utf-8") 
    attrs['{http://www.w3.org/1999/xlink}href'] = data_string
    
    image_elt = ET.Element('image', attrs)
    
    return [image_elt]
    
"""
Takes in a command and a rect (may be less restricted in the future) in a group
and changes the style attribute based. Each keyword argument in the command
becomes a style key/value, overwriting existing ones. Order of style elements
in the SVG is preserved. 
"""
class StyleFilter(ImageFilter):
  def replace(self, text, rect_elt):
    if not text.startswith('#style'):
      return
    cmd = Command(text)
    
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
    
class TemplateError(Exception):
  pass
    
class SvgTemplate:
  # a whitelist of SVG XML tags to treat as the template part
  SVG_ELEMENTS = ["g"]

  """Initialize a template from a SVG etree and list of filters to apply
  Note: filter order matters, filters are run sequentially through the tree
  (each filter is run through the whole tree before the next filter runs).
  """ 
  def __init__(self, template_etree, filters):
    self.filters = filters
    
    self.base_etree = copy.deepcopy(template_etree)
  
    # Parse template-inline configurations
    self.config = None
    
    """
    Recursively goes through elements looking for a text element with a #config
    command. Returns true if it finds one (so it can be removed by the caller),
    otherwise returns False.
    """
    def config_parse(elt):
      if strip_tag(elt.tag) in ["text", "tspan"]:
        text = get_text_contents(elt)
        if text.startswith('#config'):
          if self.config is not None:
            raise TemplateError("Duplicate config commands found: '%s', '%s'" % (self.config.cmd_str, text))
          self.config = Command(text)
          return True
        return False
      else:
        remove_list = []
        for child in elt:
          if config_parse(child):
            remove_list.append(child)
        for remove_elt in remove_list:
          elt.remove(remove_elt)
        return False
      
    config_parse(self.base_etree.getroot())
    
    if self.config is None:
      raise TemplateError("No config command found")

    # Split etree between base and template
    self.template_elts = []
    for child_elt in self.base_etree.getroot():
      if strip_tag(child_elt.tag) in self.SVG_ELEMENTS:
        self.template_elts.append(child_elt)
    for template_elt in self.template_elts:
      self.base_etree.getroot().remove(template_elt)
  
  """Returns the parsed configuration (##var = val) as a string"""
  def get_config(self, config_key):
    # TODO: more user friendly error handling
    # TODO: add description
    return self.config.get_kw_arg(config_key, "")
  
  """Returns the non-template portion of the input SVG etree."""
  def get_base(self):
    return copy.deepcopy(self.base_etree)
  
  """Instantiate the template on a input set of data (a dict of keys to values),
  returning a list of SVG etree nodes."""
  def generate(self, data_dict):
    def substitute(filter_obj, elt):
      filter_obj.apply(elt, data_dict)
      for child in elt:
        substitute(filter_obj, child)
    
    elts = copy.deepcopy(self.template_elts)
    for filter_obj in self.filters:
      for elt in elts:
        substitute(filter_obj, elt)
      
    return elts
  