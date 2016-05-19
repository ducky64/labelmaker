# labelmaker
Label sheet generator using SVG templates and CSV data.

## Example

| Template | CSV | Output |
|:---:|:---:|:---:|
| ![Image](../master/docs/template_resistors.png?raw=true) | [resistors.csv](../master/docs/resistors.csv) | ![Image](../master/docs/gen_resistors.png?raw=true) |

## Caveat Emptor
This is still in development and the API, including label template format and syntax, is subject to change. 

## Usage
`python labelmaker.py <template-svg> <csv-data> <output-filename> [--start_row=n] [--start_col=n]`

where the arguments are:

- `template-svg`: SVG template for the label. More information below.
- `csv-data`: CSV data file, one row being one label.
- `output-filename`: Output filename prefix, actual generated files will be named `output-filename_0.svg`, `output-filename_1.svg`, etc. If `.svg` is part of the output filename, the page number will be appended before the `.svg`.
- `n`: starting row or column, where zero is either the topmost row or leftmost column.

### Requirements
Works best on Python3. Barcode functionality requires PIL, a Python imaging library.

## Templates
Templates are SVG files with the page sized to the printing area and the contents of a single label placed at the "first" position. For each row in the CSV data file, the contents of the template are duplicated and shifted by a specified amount.

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
Configuration parameters are specified in the template as a text element. The label creation process will discard these elements so they will not show up in the output. The configuration syntax is:
`#config nrows=<rows> ncols=<cols> dir=<dir> incx=<increment> incy=<increment>`

- `increment` is the distance succesive labels are moved in either the y (vertical) or x\ (horizontal) direction. Positive is downwards or leftwards translation (by SVG convention). Understands standard SVG [units](https://www.w3.org/TR/SVG/coords.html#Units).
- `rows`, `cols`: number of labels in a row or column before a new row, column, or page is started.
- `dir`: either `row` or `col`, indicates the successive label increment direction.

## Copyright and acknowledgments
The following pieces of external code are used:

- `Code128.py`, a Code128 barcode image generator.

The repository-wide LICENSE does not cover external code, which have their own licenses in their respective files.
