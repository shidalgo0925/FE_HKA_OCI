# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HKADocument(models.Model):
    _name = 'hka.document'
    _description = 'Documento Electrónico HKA'
    _order = 'create_date desc'
    _rec_name = 'cufe'
    
    # Relaciones
    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        ondelete='cascade'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )
    
    # Datos del documento
    cufe = fields.Char(
        string='CUFE',
        readonly=True,
        copy=False,
        help='Código Único de Factura Electrónica'
    )
    qr_code = fields.Char(
        string='Código QR',
        readonly=True
    )
    

    def get_qr_data_uri(self):
        """Genera el QR como data URI (base64) para que aparezca en el PDF."""
        self.ensure_one()
        if not self.qr_code:
            return ''
        try:
            import qrcode
            import base64
            import io
            qr = qrcode.QRCode(version=1, box_size=4, border=2)
            qr.add_data(self.qr_code)
            qr.make(fit=True)
            img = qr.make_image(fill_color='black', back_color='white')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode('ascii')
            return 'data:image/png;base64,' + b64
        except Exception:
            return ''

    tipo_documento = fields.Selection([
        ('01', 'Factura de Operación Interna'),
        ('02', 'Factura de Importación'),
        ('03', 'Factura de Exportación'),
        ('04', 'Nota de Crédito'),
        ('05', 'Nota de Débito'),
        ('06', 'Nota de Crédito Genérica'),
        ('07', 'Nota de Débito Genérica'),
        ('08', 'Factura de Zona Franca'),
        ('09', 'Reembolso'),
    ], string='Tipo Documento', default='01')
    
    numero_documento = fields.Char(
        string='Número Documento Fiscal',
        readonly=True
    )
    
    # Estado
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviado'),
        ('authorized', 'Autorizado'),
        ('rejected', 'Rechazado'),
        ('cancelled', 'Anulado'),
    ], string='Estado', default='draft', readonly=True)
    
    # Fechas
    fecha_emision = fields.Datetime(
        string='Fecha de Emisión'
    )
    fecha_autorizacion = fields.Datetime(
        string='Fecha de Autorización',
        readonly=True
    )
    fecha_recepcion_dgi = fields.Datetime(
        string='Fecha Recepción DGI',
        readonly=True
    )
    
    # Protocolo
    numero_protocolo = fields.Char(
        string='Número Protocolo Autorización',
        readonly=True
    )
    
    # Archivos
    xml_file = fields.Binary(
        string='Archivo XML',
        attachment=True
    )
    xml_filename = fields.Char(
        string='Nombre XML'
    )
    pdf_file = fields.Binary(
        string='Archivo PDF',
        attachment=True
    )
    pdf_filename = fields.Char(
        string='Nombre PDF'
    )
    
    # Respuesta API
    response_code = fields.Char(
        string='Código Respuesta'
    )
    response_message = fields.Text(
        string='Mensaje Respuesta'
    )
    response_json = fields.Text(
        string='Respuesta JSON Completa'
    )
    
    # Anulación
    fecha_anulacion = fields.Datetime(
        string='Fecha de Anulación',
        readonly=True
    )
    motivo_anulacion = fields.Text(
        string='Motivo de Anulación'
    )
    
    def action_download_xml(self):
        """Descarga el XML del documento"""
        self.ensure_one()
        if self.xml_file:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{self._name}/{self.id}/xml_file/{self.xml_filename}?download=true',
                'target': 'self',
            }
        
        # Si no hay archivo, descargarlo de HKA
        if self.cufe:
            result = self._download_from_hka('xml')
            # Si se descargó correctamente, intentar descargar de nuevo
            if self.xml_file:
                return {
                    'type': 'ir.actions.act_url',
                    'url': f'/web/content/{self._name}/{self.id}/xml_file/{self.xml_filename}?download=true',
                    'target': 'self',
                }
            return result
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Error',
                'message': 'No hay CUFE disponible para descargar el XML',
                'type': 'danger',
            }
        }
    
    def action_download_pdf(self):
        """Descarga el PDF del documento"""
        self.ensure_one()
        if self.pdf_file:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{self._name}/{self.id}/pdf_file/{self.pdf_filename}?download=true',
                'target': 'self',
            }
        
        if self.cufe:
            # Si no hay PDF guardado, descargarlo de HKA primero
            result = self._download_from_hka('pdf')
            # Si se descargó correctamente, intentar descargar de nuevo
            if self.pdf_file:
                return {
                    'type': 'ir.actions.act_url',
                    'url': f'/web/content/{self._name}/{self.id}/pdf_file/{self.pdf_filename}?download=true',
                    'target': 'self',
                }
            return result
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Error',
                'message': 'No hay CUFE disponible para descargar el PDF',
                'type': 'danger',
            }
        }
    
    def _download_pdf_with_retry(self, max_attempts=3, delay_seconds=2):
        """Descarga PDF de HKA con reintentos (HKA a veces no devuelve PDF al instante)."""
        import time
        import logging
        _logger = logging.getLogger(__name__)
        for attempt in range(1, max_attempts + 1):
            result = self._download_from_hka('pdf')
            if result is None:
                return None
            if attempt < max_attempts:
                _logger.info(
                    'FE_HKA_OCI: Reintento %s/%s descarga PDF CUFE %s en %ss',
                    attempt, max_attempts, self.cufe, delay_seconds
                )
                time.sleep(delay_seconds)
        return result

    def _download_from_hka(self, tipo):
        """Descarga documento desde HKA"""
        from .hka_api import HKAApiClient
        import base64
        import logging
        
        _logger = logging.getLogger(__name__)
        
        company = self.company_id or self.env.company
        client = HKAApiClient(
            company.hka_usuario,
            company.hka_clave,
            company.hka_ambiente
        )
        
        result = client.descargar_documento(self.cufe, tipo)
        
        if result.get('success'):
            data = result.get('data', {})
            # HKA: API Descarga devuelve Archivo; wiki DescargaPDF devuelve Documento (PascalCase)
            archivo = (
                data.get('Archivo') or data.get('Documento') or data.get('archivo')
                or data.get('archivoBase64') or data.get('contenido') or data.get('file')
                or data.get('data') or data.get('documento') or data.get('pdf')
                or data.get('contenidoBase64')
            )
            if isinstance(data.get('Archivo'), bytes):
                archivo = data.get('Archivo')
            elif isinstance(data.get('Documento'), bytes):
                archivo = data.get('Documento')
            elif isinstance(data.get('archivo'), bytes):
                archivo = data.get('archivo')
            elif not archivo and isinstance(data.get('data'), str):
                archivo = data.get('data')

            if archivo:
                # Si viene como string base64, convertirlo a bytes
                if isinstance(archivo, str):
                    try:
                        archivo = base64.b64decode(archivo)
                    except Exception as e:
                        _logger.warning(f"Error al decodificar base64: {e}")
                        # Si falla, intentar usar el string directamente
                        pass
                
                if tipo == 'xml':
                    self.xml_file = base64.b64encode(archivo) if isinstance(archivo, bytes) else archivo
                    self.xml_filename = f'{self.cufe}.xml'
                else:
                    self.pdf_file = base64.b64encode(archivo) if isinstance(archivo, bytes) else archivo
                    self.pdf_filename = f'{self.cufe}.pdf'
                
                # Retornar None para que el método llamador pueda continuar con la descarga
                return None
            else:
                _logger.error(f"HKA API: No se encontró archivo en la respuesta. Keys: {list(data.keys())}")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': 'No se encontró archivo en la respuesta de HKA',
                        'type': 'danger',
                    }
                }
        
        error_msg = result.get('error', 'Error al descargar')
        _logger.error(f"HKA API: Error al descargar {tipo}: {error_msg}")
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Error',
                'message': error_msg,
                'type': 'danger',
            }
        }
    
    def action_check_status(self):
        """Consulta el estado del documento en HKA"""
        self.ensure_one()
        from .hka_api import HKAApiClient
        
        company = self.company_id or self.env.company
        client = HKAApiClient(
            company.hka_usuario,
            company.hka_clave,
            company.hka_ambiente
        )
        
        result = client.consultar_estado(self.cufe)
        
        if result.get('success'):
            data = result.get('data', {})
            
            estado_map = {
                'autorizado': 'authorized',
                'rechazado': 'rejected',
                'anulado': 'cancelled',
            }
            
            estado_doc = data.get('estatusDocumento', '').lower()
            if estado_doc in estado_map:
                self.state = estado_map[estado_doc]
            
            if data.get('fechaAutorizacion'):
                self.fecha_autorizacion = data.get('fechaAutorizacion')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Estado Actualizado',
                    'message': f'Estado: {self.state}',
                    'type': 'success',
                }
            }
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Error',
                'message': result.get('error', 'Error al consultar estado'),
                'type': 'danger',
            }
        }






