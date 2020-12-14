from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import HtmlFormatter
from IPython.core.magic import register_cell_magic
from IPython.display import HTML
import configparser
import json
import re

import stix2viz

import stix2generator
import stix2generator.generation.object_generator
from stix2generator.stixcustom import stix2_auto_register_all_custom


CONFIG_FILE = "config.ini"
EXTRA_SPECS = "custom_registry.json"

config_parser = configparser.SafeConfigParser()
config_parser.read(CONFIG_FILE)
tmp_config = config_parser['main']
_generator_config = stix2generator.generation.object_generator.Config(
    **tmp_config
)

with open(EXTRA_SPECS, "r", encoding="utf-8") as f:
    extra_specs = json.load(f)

stix2_auto_register_all_custom(extra_specs, "2.1")

_processor = stix2generator.create_default_language_processor(
    object_generator_config=_generator_config,
    extra_specs=extra_specs,
)


def json_print(inpt):
    string = str(inpt)
    formatter = HtmlFormatter()
    return '<style type="text/css">{}</style>{}'.format(
           formatter.get_style_defs('.highlight'),
           highlight(string, JsonLexer(), formatter))


@register_cell_magic
def stix(line, cell):
    stix_objs, var_bindings = _processor.build_graph(
        cell, return_variable_bindings=True, embed_variable_names=True
    )

    viz_config = {
        "userLabels": {
            stix_id: var_name
            for var_name, stix_ids in var_bindings.items()
            for stix_id in stix_ids
        }
    }

    viz_config_json = json.dumps(viz_config)

    output = ''
    output += ',\n'.join(map(str, stix_objs))
    if output[0] == '{':
        if len(stix_objs) > 1:
            output = '[' + output + ']'
        viz_graph = stix2viz.display(output, viz_config_json).data
        viz_graph = re.sub(r'(<svg.* style=")', r'\1border: 2px solid #ababab;', viz_graph, 1)
        return HTML(viz_graph + json_print(output))
    else:
        print(output)
