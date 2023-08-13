# labelmaker
Label sheet generator using SVG templates and CSV data.

## Superseded by [pysvglabel](https://github.com/ducky64/pysvglabel)
pysvglabel makes more consistent use of Python syntax and interprets templates as Python code to allow more powerful data transformation and SVG manipulation.
This repository is no longer developed, but if your needs are basic SVG text substitution and barcoding, this will probably still get the job done.

## Example

| Template | CSV | Output |
|:---:|:---:|:---:|
| ![Image](../master/docs/template_resistors.png?raw=true) | [resistors.csv](../master/docs/resistors.csv) | ![Image](../master/docs/gen_resistors.png?raw=true) |

## Caveat Emptor
This is still in development and the API, including label template format and syntax, is subject to change. 

## Usage
`python labelmaker.py <template-svg> <sheet-cofig> <csv-data> <output-filename> [--start_row=n] [--start_col=n] [--dir=dir]`

where the arguments are:

- `template-svg`: SVG template for the label. More information below.
- `sheet-config`: [INI-style](https://docs.python.org/3/library/configparser.html) configuration file specifying label sheet parameters.
- `csv-data`: CSV data file, one row being one label.
- `output-filename`: Output filename prefix, actual generated files will be named `output-filename_0.svg`, `output-filename_1.svg`, etc. If `.svg` is part of the output filename, the page number will be appended before the `.svg`.
- `n`: starting row or column, where zero is either the topmost row or leftmost column.
- `dir`: direction labels are incremented in, `col` (default) means top to bottom, then left to right, while `row` means left to right, then top to bottom. 

### Requirements
Works best on Python3. Barcode functionality requires PIL, a Python imaging library.

## Templates
Templates are SVG files with the page sized to a single label. For each row in the CSV data file, the contents of the template are duplicated and shifted by a specified amount.

### Syntax
The template command syntax used in this document is:

- `<>` angle brackets for a user-specified value.
- `[]` square brackets for optional content.
- Everything else should be taken literally. In particular, `#`, and `%` have special meaning.

### Filters
Filters modify element(s) in a template instance based on data in the CSV row. These filters are currently available (and are automatically run as part of `labelmaker.py`):

- Text filter: in a CSV text element, does Python-style string interpolation. For example, if the CSV had a row called `num`, this would replace all text instances of `%(num)` with the `num` value in that row.
- Image filter: a class of filters which replace a image placeholder with an image. An image placeholder is a SVG group containing only a rectangle (indicating image extents) and text element (containing the command).
- code128 filter: an image filter, where the command syntax is `#code128 [align=<align>] [quiet=<quiet>] <text>`. `align` is directly inserted into the resulting image element as `preserveAspectRatio` (see SVG spec [here](https://www.w3.org/TR/SVG/coords.html#PreserveAspectRatioAttribute)), which specifies image resizing / alignment. `quiet` (either `true` or `false`) indicates whether or not to generate the Code128 quiet zone as part of the image. `text` is the contents of the barcode (this may be a text filter style string interpolation command, allowing generation of barcodes from CSV data). No human-readable text will be generated, though you can add it as a separate text element.
- Style filter: takes in a group containing an element (currently limited to rectangles) and a text element (containing the command), alters `style` components (see SVG spec [here](https://www.w3.org/TR/SVG/styling.html)). Command syntax is `#style [<style-name>=<new-style-val>]`, where the style name - value pairs can be repeated. Replaces the existing style property if one exists, otherwise adds it to the property list.

### Configuration
Configuration parameters used to be specified in the label templates, but have been moved to a separate file. The `#config` command will now cause an error. Having configurations in a separate file allows the SVG templates to be sized to a single label (which may help design) and allows the same template to generate to different sized sheets.

## Sheet Configuration
Sheet configuration specify the sheet parameters, like the page size, how many labels are in a sheet, and the spacing between labels. See the `config/` folder for examples. Note that fields that expect a length parameter understands [SVG units](https://www.w3.org/TR/SVG/coords.html#Units), so an input like `1 mm` is valid.

These are options in the `[sheet]` section:
- `sizex`, `sizey`: page size.
- `offx`, `offy`: offset distance to first label from top left of page. Positive is rightwards and downwards (by SVG convention).
- `incx`, `incy`: distance between successive labels, this does NOT take into account size of the templates (so a 0 entry means labels will be overlapped!). Positive is rightwards and downwards (by SVG convention).
- `nrows`, `ncols`: number of labels in a row, or column before a new column, row, or page is started.


## Copyright and acknowledgments
The following pieces of external code are used:

- `Code128.py`, a Code128 barcode image generator.

The repository-wide LICENSE does not cover external code, which have their own licenses in their respective files.
