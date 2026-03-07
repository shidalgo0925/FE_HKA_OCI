# -*- coding: utf-8 -*-
from . import models
from . import wizard
from .data.load_panama_locations import load_panama_locations


def _cargar_codigos_ubicacion_si_faltan(env):
    """Carga códigos de ubicación desde XML solo si no existen (instalación idempotente en cualquier DB)."""
    import os
    import xml.etree.ElementTree as ET
    import logging
    _logger = logging.getLogger(__name__)
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    xml_path = os.path.join(addon_dir, 'data', 'hka_codigo_ubicacion_data.xml')
    if not os.path.isfile(xml_path):
        return
    tree = ET.parse(xml_path)
    root = tree.getroot()
    Model = env['hka.codigo.ubicacion']
    creados = 0
    for rec in root.iter('record'):
        if rec.get('model') != 'hka.codigo.ubicacion':
            continue
        vals = {}
        for field in rec.findall('field'):
            name = field.get('name')
            text = (field.text or '').strip()
            if name == 'activo':
                vals[name] = text.lower() in ('1', 'true', 'yes')
            elif name and text:
                vals[name] = text
        codigo = vals.get('codigo')
        if not codigo:
            continue
        if Model.search([('codigo', '=', codigo)], limit=1):
            continue
        Model.create(vals)
        creados += 1
    if creados:
        _logger.info('FE_HKA_OCI: Cargados %s códigos de ubicación (solo los faltantes).', creados)


# post_init_hook reemplazado por load_panama_locations (data/load_panama_locations.py)
