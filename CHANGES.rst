Changelog
=========

2.0.1 (2020-12-18)
------------------

- Handle custom destination path.
  [cekk]

2.0.0 (2020-07-28)
------------------

- Heavy refactoring for python3 compatibility.
  [cekk]
- Allow to import users and groups.
  [cekk]
- Remove unmaintained dependencies and move needed code here.
  [cekk]

1.0.5 (2019-03-19)
------------------

- fixed fix_link_noreference function.
  [eikichi18]


1.0.4 (2019-02-08)
------------------

- Added fix for links without any references. Added dedicated report after migration.
  [daniele]

- Added check in schemaupdater for leave field empty when value is empty.
  [eikichi18]

- Fix broken links generation list.
  [cekk]


1.0.3 (2018-10-18)
------------------

- Added json item to adapters methods.
  [daniele]


1.0.2 (2018-10-11)
------------------

- Fixed mapping for link internal/external link.
  [eikichi18]


1.0.1 (2018-10-09)
------------------

- Fix uudi matcher after migration.
  [eikichi18]


1.0.0 (2018-10-04)
------------------

- Add check if Plone Site element was indexed.
- Add support for specific context steps with adapters.
  [cekk]


1.0a4 (2018-09-03)
------------------

- Handle cases where exlude-type is not set.
  [cekk]
- Generate a list of broken links in tinymce after migration,
  and expose them in final report view.
  [cekk]

1.0a3 (2018-07-19)
------------------

- Added check for element's father data.
  [eikichi18]


1.0a2 (2018-07-03)
------------------

- Break migration if doesn't find a content types.
  [eikichi18]


1.0a1 (2018-06-19)
------------------

- Initial release.
  [eikichi18]
