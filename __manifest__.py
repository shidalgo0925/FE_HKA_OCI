# -*- coding: utf-8 -*-
{
    'name': 'ETS Facturación Electrónica Panamá - HKA',
    'version': '18.0.1.1.0',
    'category': 'Accounting/Localizations/EDI',
    'summary': 'Integración con The Factory HKA para Facturación Electrónica de Panamá',
    'description': """
Facturación Electrónica Panamá - HKA Factory
=============================================

Este módulo permite la emisión de facturas electrónicas en Panamá
mediante la integración con el proveedor autorizado The Factory HKA Corp.

Características:
----------------
* Configuración de credenciales HKA
* Envío de facturas electrónicas a la DGI
* Obtención de CUFE (Código Único de Factura Electrónica)
* Descarga de XML y PDF autorizados
* Anulación de documentos electrónicos
* Consulta de estado de documentos
* Historial de transacciones

Requisitos:
-----------
* Cuenta activa en The Factory HKA
* Licencia de facturación electrónica vigente
* Certificado digital (para producción)

Desarrollado por: Easytech Services
    """,
    'author': 'Easytech Services',
    'website': 'https://easytech.services',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'product',
        'account',
        'contacts',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/factulectronic_security.xml',
        'data/ir_sequence_data.xml',
        'data/hka_tipo_documento_data.xml',
        'data/hka_cpbs_data.xml',
        'data/hka_unidad_medida_data.xml',
        'views/hka_codigo_ubicacion_views.xml',
        'views/hka_cpbs_views.xml',
        'views/hka_unidad_medida_views.xml',
        'views/product_category_views.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'wizard/hka_cancel_wizard_view.xml',
        'views/hka_document_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/menu_views.xml',
        'report/invoice_report.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/icon.png'],
    'external_dependencies': {
        'python': ['requests', 'PyJWT'],
    },
    'post_init_hook': 'load_panama_locations',
}






