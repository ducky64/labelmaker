import copy
import re

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
    if strip_tag(elt.tag) in ['text', 'tspan'] and elt.text:
      def parsed(match):
        key = match.group(1)
        # TODO: more robust error handling
        assert key in data_dict
        return data_dict[key]
      elt.text = re.sub(r"%\((.+)\)", parsed, elt.text)

"""Replaces a group which consists of only a textbox (image replacement command)
and rectangle (image sizing) with an image
The rectangle is replaced with the image, and the text element is removed (this
preserves any transforms within the group)."""
class ImageFilter(TemplateFilter):
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
      
    # TODO image substitution
    print(get_text_contents(text_elt))

class BarcodeFilter(ImageFilter):
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
    self.config = {}
    def parsed(match):
      key = match.group(1)
      val = match.group(2)
      assert key not in self.config, "duplicate key %s" % key
      self.config[key] = val
      print("found config: %s = '%s'" % (key, val))
      return ""
    
    def config_parse(elt):
      if strip_tag(elt.tag) in ["text", "tspan"] and elt.text:
        elt.text = re.sub(r"##(\S+)\s*=\s*(\S+)", parsed, elt.text)
      for child in elt:
        config_parse(child)
      
    config_parse(self.base_etree.getroot())

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
    assert config_key in self.config
    return self.config[config_key]
  
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
  