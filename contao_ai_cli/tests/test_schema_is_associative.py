"""`eval.isAssociative`: the index of a list is the value, the text the label.

Contao's `tl_page.useSSL` declares `array('http://', 'https://')` with
`isAssociative` and stores 0/1. `schema show` listed the labels, so a caller
building `--set useSSL=...` from it had nothing it could pass (Nr. 53, found
live on web.werk.wien on 2026-09-17; the core bundle refused `useSSL=1` for the
same reason and is fixed in v0.21.1).

The field definitions below are what `parse_vardump` makes of
`debug:dca tl_page fields` on Contao 5.7.13 (c5, 2026-09-17).
"""

from contao_ai_cli.core.dca_schema import _build_field_entry

USE_SSL = {
    'inputType': 'select',
    'options': {0: 'http://', 1: 'https://'},
    'eval': {'tl_class': 'w50', 'isAssociative': True},
    'sql': {'type': 'boolean', 'default': True},
    'label': {0: 'Protocol', 1: 'Here you can select which protocol to use for the website.'},
}

SITEMAP = {
    'inputType': 'select',
    'options': {0: 'map_default', 1: 'map_always', 2: 'map_never'},
    'eval': {'tl_class': 'w50'},
}


def test_a_list_declared_associative_maps_the_index_to_its_label():
    assert _build_field_entry('useSSL', USE_SSL)['options'] == {'0': 'http://', '1': 'https://'}


def test_a_plain_list_still_gives_its_values():
    assert _build_field_entry('sitemap', SITEMAP)['options'] == ['map_default', 'map_always', 'map_never']


def test_integer_keys_that_are_not_0_to_n_are_values_not_positions():
    # `array(6 => 'ConpAI Hero')`: 6 is the value. The comment promised a list only
    # "if sequential" and checked nothing, so this came back as ['ConpAI Hero'] —
    # the image-size trap the core bundle closed in v0.16.0 (Fable review, v0.22.1).
    fdef = {'options': {6: 'ConpAI Hero', 9: 'Teaser'}}
    assert _build_field_entry('size', fdef)['options'] == {'6': 'ConpAI Hero', '9': 'Teaser'}


def test_an_associative_dca_array_is_unchanged():
    fdef = {'options': {'de': 'Deutsch', 'en': 'English'}, 'eval': {'isAssociative': True}}
    assert _build_field_entry('language', fdef)['options'] == {'de': 'Deutsch', 'en': 'English'}
