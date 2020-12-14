templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'

project = 'stix2-generator'
copyright = '2020, OASIS Open'
author = 'OASIS Open'

version = '0.1.0'
release = '0.1.0'

language = None
exclude_patterns = ['_build', '_templates', 'Thumbs.db', '.DS_Store']
pygments_style = 'sphinx'
todo_include_todos = False

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx-prompt',
]

html_theme = 'alabaster'
html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'relations.html',
        'searchbox.html',
    ]
}

latex_elements = {}
latex_documents = [
    (master_doc, 'stix2-generator.tex', 'stix2-generator Documentation',
     author, 'manual'),
]

man_pages = [
    (master_doc, project, 'stix2-generator Documentation', [author], 1),
]
