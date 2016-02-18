# labelmaker
Label sheet generator using SVG templates and CSV data.

## Caveat Emptor
This is still in development and the API, including label template format and syntax, is subject to change. 

## Usage
`python labelmaker.py <template svg> <csv data> <output filename>`

where the arguments are:

- `template svg`: SVG template for the label. More information below.
- `CSV data`: CSV data file, one row being one label.
- `output filename`: should be obvious, will overwrite if the file already exists.

### Requirements
Works best on Python3. Barcode functionality requires PIL, a Python imaging library.

## Syntax
The command syntax used in this document is:

- `<>` angle brackets for a user-specified value.
- `[]` square brackets for optional content.
- Everything else should be taken literally. In particular, `##`, `#`, `@`, and `%` all have special meaning.

## Templates
Templates are SVG files with the page sized to the printing area and the contents of a single label placed at the "first" position. For each row in the CSV data file, the contents of the template are duplicated and shifted by a specified amount.

### Filters
Filters modify element(s) in a template instance based on data in the CSV row. These filters are currently available:

- Text filter: in a CSV text element, does Python-style string interpolation. For example, if the CSV had a row called `num`, this would replace all text instances of `%(num)` with the `num` value in that row.
- Image filter: a class of filters which replace a image placeholder: a SVG group containing only a rectangle, indicating the extends, and a text element, indicating a command.
- code128 filter: an image filter, where the command syntax is `#code128 [@align=<align>] <text>`. The optional `align` parameter is directly inserted into the resulting image as `preserveAspectRatio`, which specifies image resizing / alignment. The text is the contents of the barcode. No human-readable text will be generated, though that can be added separately as a text element.

### Configuration
Configuration parameters can be specified in the template as a text element. The label creation process will discard these elements so they will not show up in the output. The configuration options are:

- `##incx=<increment>`: distance successive labels are moved by in the y- (vertical) direction. Positive is downwards translation, by SVG convention. 
- `##incy=<increment>`: distance successive columns of labels are moved by in the x- (horizontal) direction. Positive is leftwards translation, by SVG convention.
- `##nrows=<number>`: number of labels in a row before a new column is started.
- `##ncols=<number>`: number of columns before a new page is started. 

## Copyright and acknowledgments
The following pieces of external code are used:

- `Code128.py`, a Code128 barcode image generator.

The repository-wide LICENSE does not cover external code, which have their own licenses in their respective files.
