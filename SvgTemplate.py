import copy
import re

"""Removes the namespace from a XML tag"""
def strip_tag(tag):
  if "}" in tag:
    return tag.split('}', 1)[1]
  else:
    return tag

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
    if strip_tag(elt.tag) in ["text", "tspan"] and elt.text:
      def parsed(match):
        key = match.group(1)
        # TODO: more robust error handling
        assert key in data_dict
        print(key + data_dict[key])
        return data_dict[key]
      elt.text = re.sub(r"%\((.+)\)", parsed, elt.text)

class SvgTemplate:
  # a whitelist of SVG XML tags to treat as the template part
  SVG_ELEMENTS = ["g"]

  """Initialize a template from a SVG etree""" 
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
  
  """Returns the non-template portion of the input SVG etree."""
  def get_base(self):
    return copy.deepcopy(self.base_etree)
  
  """Instantiate the template on a input set of data (a dict of keys to values),
  returning a list of SVG etree nodes."""
  def generate(self, data_dict):
    def substitute(elt):
      for filter_obj in self.filters:
        filter_obj.apply(elt, data_dict)
      for child in elt:
        substitute(child)
    
    elts = copy.deepcopy(self.template_elts)
    for elt in elts:
      substitute(elt)
      
    return elts
  