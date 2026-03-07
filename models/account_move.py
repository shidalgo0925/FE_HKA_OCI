# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json
import re
from datetime import datetime
import pytz
from dateutil import parser

_logger = logging.getLogger(__name__)

RUC_REGEX = re.compile(r"^\d+(-\d+){1,2}$")


def _normalize_ruc(vat):
    if not vat:
        return None
    vat = vat.strip().replace(".", "").replace(" ", "").upper()
    if "D.V" in vat:
        vat = vat.split("D.V")[0].strip()
    return vat or None


def _is_valid_ruc(vat):
    if not vat:
        return False
    return RUC_REGEX.match(vat) is not None


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    # Campos de facturación electrónica
    hka_document_id = fields.Many2one(
        'hka.document',
        string='Documento HKA',
        copy=False
    )
    
    hka_cufe = fields.Char(
        string='CUFE',
        related='hka_document_id.cufe',
        store=True,
        copy=False
    )
    
    hka_state = fields.Selection(
        related='hka_document_id.state',
        string='Estado FE',
        store=True
    )
    
    hka_tipo_documento = fields.Selection([
        ('01', 'Factura de Operación Interna'),
        ('02', 'Factura de Importación'),
        ('03', 'Factura de Exportación'),
        ('04', 'Nota de Crédito'),
        ('05', 'Nota de Débito'),
        ('06', 'Nota de Crédito Genérica'),
        ('07', 'Nota de Débito Genérica'),
        ('08', 'Factura de Zona Franca'),
        ('09', 'Reembolso'),
    ], string='Tipo Documento FE', default='01')
    
    hka_naturaleza_operacion = fields.Selection([
        ('01', 'Venta'),
        ('02', 'Exportación'),
        ('10', 'Transferencia'),
        ('11', 'Devolución'),
        ('12', 'Consignación'),
        ('13', 'Remesa'),
        ('14', 'Entregas Gratuitas'),
        ('20', 'Compra'),
        ('21', 'Importación'),
    ], string='Naturaleza Operación', default='01')
    
    hka_tipo_operacion = fields.Selection([
        ('1', 'Salida'),
        ('2', 'Entrada'),
    ], string='Tipo Operación', default='1')
    
    hka_destino_operacion = fields.Selection([
        ('1', 'Panamá'),
        ('2', 'Extranjero'),
    ], string='Destino Operación', default='1')
    
    hka_forma_pago = fields.Selection([
        ('01', 'Crédito'),
        ('02', 'Contado'),
        ('03', 'Tarjeta Crédito'),
        ('04', 'Tarjeta Débito'),
        ('05', 'ACH'),
        ('06', 'Vale'),
        ('07', 'Otro'),
        ('08', 'Efectivo'),
        ('09', 'Pago Móvil'),
        ('99', 'No Aplica'),
    ], string='Forma de Pago', default='02')
    
    # Campos de referencia para NC/ND
    hka_documento_referencia = fields.Char(
        string='CUFE Documento Referencia',
        help='CUFE del documento original para NC/ND'
    )
    hka_fecha_documento_referencia = fields.Date(
        string='Fecha Documento Referencia'
    )
    hka_estado_dgi = fields.Selection([
        ('pendiente', 'Pendiente'),
        ('autorizado', 'Autorizado'),
        ('anulado', 'Anulado'),
        ('error', 'Error'),
    ], string='Estado DGI', compute='_compute_hka_estado_dgi', store=True, copy=False)
    hka_motivo_anulacion = fields.Text(
        string='Motivo Anulación DGI',
        copy=False
    )

    @api.depends('hka_document_id', 'hka_document_id.state')
    def _compute_hka_estado_dgi(self):
        mapping = {
            'authorized': 'autorizado',
            'cancelled': 'anulado',
            'rejected': 'error',
            'sent': 'pendiente',
            'draft': 'pendiente',
        }
        for move in self:
            if not move.hka_document_id:
                move.hka_estado_dgi = 'pendiente'
            else:
                move.hka_estado_dgi = mapping.get(move.hka_document_id.state, 'pendiente')

    def _get_hka_fecha_emision(self):
        """Obtiene la fecha de emisión en formato HKA
        
        HKA requiere fecha y hora en formato ISO 8601 con timezone UTC-5 (Panamá)
        Formato: YYYY-MM-DDTHH:MM:SS-05:00
        """
        self.ensure_one()
        
        # Obtener zona horaria de Panamá
        panama_tz = pytz.timezone('America/Panama')
        
        # Usar la fecha/hora actual en zona horaria de Panamá
        fecha_emision = datetime.now(panama_tz)
        
        # Formato ISO 8601 con timezone: YYYY-MM-DDTHH:MM:SS-05:00
        # Panamá siempre es UTC-5, así que usamos -05:00 directamente
        fecha_str = fecha_emision.strftime('%Y-%m-%dT%H:%M:%S-05:00')
        
        return fecha_str
    
    def _get_hka_fecha_referencia(self):
        """Obtiene la fecha de documento de referencia en formato HKA"""
        self.ensure_one()
        if not self.hka_fecha_documento_referencia:
            return ""
        
        panama_tz = pytz.timezone('America/Panama')
        fecha_ref = datetime.combine(self.hka_fecha_documento_referencia, datetime.min.time())
        fecha_ref = panama_tz.localize(fecha_ref)
        return fecha_ref.strftime('%Y-%m-%d')
    
    def _clean_html_text(self, text):
        """Limpia HTML del texto para HKA - espera texto plano"""
        if not text:
            return ""
        import re
        # Remover todas las etiquetas HTML
        texto_limpio = re.sub(r'<[^>]+>', '', text)
        # Limpiar espacios múltiples
        texto_limpio = ' '.join(texto_limpio.split())
        return texto_limpio

    def _clean_phone_for_hka(self, phone):
        """Formato HKA: 999-9999 o 9999-9999 (7-12 chars). Si no cumple, devuelve None para no enviar."""
        if not phone:
            return None
        import re
        digits = re.sub(r'\D', '', str(phone))[:12]
        if len(digits) == 7:
            return f"{digits[:3]}-{digits[3:]}"
        if len(digits) == 8:
            return f"{digits[:4]}-{digits[4:]}"
        if len(digits) in (10, 11, 12):
            return f"{digits[-8:-4]}-{digits[-4:]}" if len(digits) >= 8 else None
        return None
    
    def _get_hka_client(self):
        """Obtiene el cliente de la API HKA"""
        from .hka_api import HKAApiClient
        
        company = self.company_id or self.env.company
        
        if not company.hka_usuario or not company.hka_clave:
            raise UserError(_('Configure las credenciales de HKA en Ajustes.'))
        
        return HKAApiClient(
            company.hka_usuario,
            company.hka_clave,
            company.hka_ambiente
        )
    
    # def _prepare_hka_cliente(self):
    #     """Prepara los datos del cliente para HKA"""
    #     self.ensure_one()
    #     partner = self.partner_id

    #     tipo_cliente = partner.pa_tipo_cliente_fe or "02"

    #     # =========================
    #     # RUC
    #     # =========================
    #     ruc = partner.pa_ruc or partner.vat or ""
    #     ruc = ruc.strip() if ruc else ""

    #     # Consumidor Final sin RUC → enviar 00000
    #     if tipo_cliente == "02" and not ruc:
    #         ruc = "00000"

    #     # =========================
    #     # Tipo Contribuyente
    #     # =========================
    #     if tipo_cliente == "04":
    #         tipo_contribuyente_hka = None
    #     elif tipo_cliente == "02":
    #         tipo_contribuyente_hka = "1"
    #     else:
    #         tipo_contribuyente_hka = partner.pa_tipo_ruc or "2"

    #     # =========================
    #     # Construcción base cliente
    #     # =========================
    #     cliente_data = {
    #         "tipoClienteFE": str(tipo_cliente),
    #         "numeroRUC": str(ruc),
    #         "digitoVerificadorRUC": str(partner.pa_dv) if partner.pa_dv else "",
    #         "razonSocial": str(partner.name) if partner.name else "",
    #         "direccion": str(partner.street) if partner.street else "",
    #         "provincia": str(partner.state_id.name) if partner.state_id and partner.state_id.name else "",
    #         "distrito": str(partner.city) if partner.city else "",
    #         "corregimiento": str(partner.pa_corregimiento) if partner.pa_corregimiento else "",
    #         "correoElectronico1": str(partner.email) if partner.email else "",
    #         "telefono1": self._clean_phone_for_hka(partner.phone) if partner.phone else "",
    #         "pais": str(partner.country_id.code) if partner.country_id and partner.country_id.code else "PA",
    #     }

    #     if tipo_contribuyente_hka is not None:
    #         cliente_data["tipoContribuyente"] = str(tipo_contribuyente_hka)

    #     # =========================
    #     # Código Ubicación NORMALIZADO (ACEPTA 8-8-6 y 08-08-06)
    #     # =========================
    #     if partner.pa_codigo_ubicacion_id:
    #         codigo = partner.pa_codigo_ubicacion_id.codigo
    #     else:
    #         codigo = partner.pa_codigo_ubicacion

    #     if codigo:
    #         codigo = codigo.strip()

    #         import re
    #         match = re.match(r'^(\d{1,2})-(\d{1,2})-(\d{1,2})$', codigo)

    #         # if match:
    #         #     # Convertir a formato limpio sin ceros a la izquierda
    #         #     provincia = str(int(match.group(1)))
    #         #     distrito = str(int(match.group(2)))
    #         #     corregimiento = str(int(match.group(3)))

    #         #     codigo_normalizado = f"{provincia}-{distrito}-{corregimiento}"
    #         #     cliente_data["codigoUbicacion"] = codigo_normalizado
    #         # else:
    #         #     raise UserError(
    #         #         _("El Código de Ubicación debe tener formato N-N-N "
    #         #         "(ej: 8-8-6 o 08-08-06).")
    #         #     )
                
    #         # ==========================================
    #         # HARDCODE TEMPORAL PARA PRUEBA
    #         # ==========================================
    #         cliente_data["codigoUbicacion"] = "8-8-6"
    #         _logger.warning("⚠️ codigoUbicacion HARDCODEADO a 8-8-6 para prueba")

    #     return cliente_data

    def _prepare_hka_cliente(self):
        """Prepara los datos del cliente para HKA. RUC normalizado y validado (evitar 1601/1602)."""
        self.ensure_one()
        partner = self.partner_id
        tipo_cliente = partner.pa_tipo_cliente_fe or "02"

        ruc = _normalize_ruc(partner.vat or partner.pa_ruc)
        ruc_valido = ruc and _is_valid_ruc(ruc)

        # Código Ubicación: no modificar (instrucción)
        codigo_ubicacion = (partner.hka_codigo_ubicacion or "").strip()
        if not codigo_ubicacion and tipo_cliente in ("01", "03"):
            raise UserError(_("El cliente no tiene código de ubicación HKA. Configúrelo en el contacto."))
        if not codigo_ubicacion:
            codigo_ubicacion = "8-8-1"
        codigo_limpio = re.sub(r'[^\d]', '', codigo_ubicacion)
        if len(codigo_limpio) == 6 and '-' not in codigo_ubicacion:
            codigo_ubicacion = f"{int(codigo_limpio[0:2])}-{int(codigo_limpio[2:4])}-{int(codigo_limpio[4:6])}"

        cliente_data = {
            "codigoUbicacion": codigo_ubicacion,
            "razonSocial": str(partner.name) if partner.name else "",
            "direccion": str(partner.street) if partner.street else "",
            "provincia": str(partner.state_id.name) if partner.state_id and partner.state_id.name else "",
            "distrito": str(partner.city) if partner.city else "",
            "corregimiento": str(partner.pa_corregimiento) if partner.pa_corregimiento else "",
            "correoElectronico1": str(partner.email) if partner.email else "",
            "pais": str(partner.country_id.code) if partner.country_id and partner.country_id.code else "PA",
        }
        telefono_hka = self._clean_phone_for_hka(partner.phone)
        if telefono_hka:
            cliente_data["telefono1"] = telefono_hka

        if tipo_cliente == "02":
            cliente_data["tipoClienteFE"] = "02"
            cliente_data["numeroRUC"] = "00000"
            cliente_data["tipoContribuyente"] = "1"
            cliente_data.pop("telefono1", None)
        elif tipo_cliente == "04":
            cliente_data["tipoClienteFE"] = "04"
            cliente_data["numeroRUC"] = ruc if ruc_valido else "0"
        else:
            if not ruc_valido:
                cliente_data["tipoClienteFE"] = "02"
                cliente_data["numeroRUC"] = "00000"
                cliente_data["tipoContribuyente"] = "1"
                cliente_data.pop("telefono1", None)
            else:
                cliente_data["tipoClienteFE"] = str(tipo_cliente)
                cliente_data["numeroRUC"] = ruc
                cliente_data["tipoContribuyente"] = partner.pa_tipo_ruc or "2"
                if partner.pa_dv:
                    cliente_data["digitoVerificadorRUC"] = str(partner.pa_dv).strip()
                else:
                    cliente_data["digitoVerificadorRUC"] = ""

        return cliente_data
   
    def _prepare_hka_items(self):
        """Prepara las líneas de la factura para HKA conforme a DGI Panamá"""
        self.ensure_one()
        items = []

        valid_lines = self.invoice_line_ids.filtered(
            lambda l: not l.display_type or l.display_type == 'product'
        )

        for idx, line in enumerate(valid_lines, 1):

            product = line.product_id

            if not product:
                raise UserError(_("La línea %s no tiene producto asignado.") % idx)

            # CPBS: DGI XML usa dCodCPBScmp (4 chars) y dCodCPBSabr (2 chars). HKA valida esas longitudes.
            tmpl = product.product_tmpl_id
            cpbs_rec = tmpl.hka_cpbs_id or (tmpl.categ_id and tmpl.categ_id.hka_cpbs_id)
            raw_cpbs = (cpbs_rec.code or "99990000").strip() if cpbs_rec else "99990000"
            base_8 = raw_cpbs.zfill(8)[:8]
            codigo_cpbs = base_8[:4]
            codigo_cpbs_abrev = base_8[:2]

            # Unidad de medida: desde catálogo hka.unidad.medida del producto
            uom_hka = tmpl.hka_unidad_medida_id
            unidad_medida = (uom_hka.code or "und").strip() if uom_hka else "und"

            # Tipo Item
            tipo_item = "S" if product.type == "service" else "B"

            # ITBMS
            tax_amount = 0.0
            tasa_itbms = "00"

            if tipo_item == "B":
                for tax in line.tax_ids:
                    if tax.amount > 0:
                        tax_amount = round(line.price_subtotal * (tax.amount / 100), 2)

                        if tax.amount == 7:
                            tasa_itbms = "01"
                        elif tax.amount == 10:
                            tasa_itbms = "02"
                        elif tax.amount == 15:
                            tasa_itbms = "03"

            precio_item = round(line.price_subtotal, 2)
            valor_total_item = round(precio_item + tax_amount, 2)

            descuento_monto = 0.0
            if line.discount > 0:
                descuento_monto = round(
                    line.price_unit * line.quantity * (line.discount / 100.0),
                    2
                )

            item = {
                "descripcion": line.name or product.name,
                "codigo": product.default_code or str(idx).zfill(3),
                "tipoItem": tipo_item,
                "cantidad": f"{line.quantity:.2f}",
                "precioUnitario": f"{line.price_unit:.2f}",
                "precioUnitarioDescuento": f"{descuento_monto:.2f}",
                "precioItem": f"{precio_item:.2f}",
                "valorTotal": f"{valor_total_item:.2f}",
                "tasaITBMS": tasa_itbms,
                "valorITBMS": f"{tax_amount:.2f}",
                "unidadMedida": unidad_medida,
            }
            item["codigoCPBS"] = codigo_cpbs
            item["codigoCPBSAbrev"] = codigo_cpbs_abrev

            items.append(item)

        return items
    
    def _prepare_hka_totales(self):
        """Prepara los totales para HKA"""
        self.ensure_one()
        
        # Calcular ITBMS solo para bienes (no servicios)
        # Servicios son exentos según regla DGI/HKA Panamá
        valid_lines = self.invoice_line_ids.filtered(
            lambda l: not l.display_type or l.display_type == 'product'
        )
        
        total_itbms = 0
        for line in valid_lines:
            # Solo aplicar ITBMS si NO es servicio
            is_service = line.product_id and line.product_id.type == 'service'
            if not is_service:
                # Calcular ITBMS solo para bienes
                total_itbms += (line.price_total - line.price_subtotal)
        
        # totalFactura = totalPrecioNeto + totalITBMS
        # Para servicios exentos: totalFactura = totalPrecioNeto (sin ITBMS)
        total_factura = self.amount_untaxed + total_itbms
        
        # Calcular totalTodosItems: Suma de valorTotal de todos los items
        # Según documentación: "Total de todos los Ítems (Suma de ValorTotal)"
        # IMPORTANTE: Debe coincidir EXACTAMENTE con la suma de valorTotal de cada item
        # valorTotal en item = precioItem + valorITBMS (según _prepare_hka_items)
        total_todos_items = 0.0
        for line in valid_lines:
            precio_item = line.price_subtotal
            # Calcular ITBMS solo para bienes (no servicios)
            is_service = line.product_id and line.product_id.type == 'service'
            if not is_service:
                valor_itbms_item = line.price_total - line.price_subtotal
            else:
                valor_itbms_item = 0.0
            valor_total_item = precio_item + valor_itbms_item
            total_todos_items += valor_total_item
        
        # Construir totales según documentación oficial HKA
        # totalMontoGravado: SI, N|1..11|1.2 - Suma de TotalITBMS, TotalISC y valorTotalOTI
        # Como no hay ISC ni OTI, totalMontoGravado = totalITBMS
        total_monto_gravado = total_itbms  # Suma de TotalITBMS + TotalISC (0) + valorTotalOTI (0)
        
        totales = {
            "totalPrecioNeto": f"{self.amount_untaxed:.2f}",  # SI, N|1..11|1.2 - Suma de PrecioItem
            "totalITBMS": f"{total_itbms:.2f}",  # SI, N|1..11|2 - Suma de ValorITBMS
            "totalMontoGravado": f"{total_monto_gravado:.2f}",  # SI, N|1..11|1.2 - Suma de TotalITBMS, TotalISC y valorTotalOTI
            # totalISC: SI, N|1..11|1.2 - NO enviar si es 0.00 (según documentación)
            "totalFactura": f"{total_factura:.2f}",  # SI, N|1..11|1.2 - TotalPrecioNeto + TotalITBMS + TotalISC - TotalDescuento
            "totalValorRecibido": f"{total_factura:.2f}",  # SI, N|1..11|1.2 - Suma de valorCuotaPagada
            "vuelto": "0.00",  # C/C, N|1..11|1.2 - Diferencia entre TotalValorRecibido y TotalFactura
            "tiempoPago": "1" if (self.hka_forma_pago or "02") == "02" else "2",  # SI, N|1: 1:Inmediato, 2:Plazo, 3:Mixto
            "nroItems": str(len(valid_lines)),  # SI, N|1..11 - Número total de ítems
            "totalTodosItems": f"{total_todos_items:.2f}",  # SI, N|1..11|1.2 - Suma de ValorTotal de todos los items
        }
        
        return totales
    
    def _prepare_hka_documento(self):
        """Prepara el documento completo para HKA"""
        self.ensure_one()
        company = self.company_id or self.env.company
        
        # Obtener número de documento fiscal
        # Según documentación: N|10, de 0000000001 a 9999999999, llenar con ceros a la izquierda
        sequence = self.env['ir.sequence'].sudo().next_by_code('hka.documento.fiscal')
        if not sequence:
            sequence = str(self.id).zfill(10)
        # Asegurar que tenga exactamente 10 dígitos
        numero_documento_fiscal = str(sequence).zfill(10)[:10]
        
        # puntoFacturacionFiscal: Según documentación: N|3, llenar con ceros a la izquierda
        punto_facturacion = str(company.hka_punto_facturacion or "001").zfill(3)[:3]
        
        documento = {
            "codigoSucursalEmisor": company.hka_codigo_sucursal or "0000",
            "tipoSucursal": company.hka_tipo_sucursal or "1",
            "datosTransaccion": {
                "tipoEmision": "01",
                "tipoDocumento": self.hka_tipo_documento or "01",
                "numeroDocumentoFiscal": numero_documento_fiscal,
                "puntoFacturacionFiscal": punto_facturacion,
                "fechaEmision": self._get_hka_fecha_emision(),
                "naturalezaOperacion": self.hka_naturaleza_operacion or "01",
                "tipoOperacion": self.hka_tipo_operacion or "1",
                "destinoOperacion": self.hka_destino_operacion or "1",
                "formatoCAFE": company.hka_formato_cafe or "1",
                "entregaCAFE": company.hka_entrega_cafe or "1",
                "envioContenedor": "1",
                "procesoGeneracion": "1",
                "tipoVenta": "1",
                "informacionInteres": self._clean_html_text(self.narration or ""),

                # 🔥 CLIENTE VA AQUÍ
                "cliente": self._prepare_hka_cliente(),
            },

            "listaItems": self._prepare_hka_items(),
            "totalesSubTotales": self._prepare_hka_totales(),
        }
        
        # listaFormaPago debe estar en totalesSubTotales según documentación oficial HKA
        # Calcular valorCuotaPagada después de tener totales
        total_factura = documento["totalesSubTotales"]["totalFactura"]
        forma_pago = self.hka_forma_pago or "02"
        # descFormaPago: C/C, AN|10..100 - Obligatorio solo si formaPagoFact = 99
        # Si no es 99, NO enviar el campo o enviarlo vacío (según documentación)
        desc_forma_pago = ""
        if forma_pago == "99":  # Otro - requiere descripción
            desc_forma_pago = "Otro método de pago"  # Mínimo 10 caracteres
        
        documento["totalesSubTotales"]["listaFormaPago"] = [{
            "formaPagoFact": forma_pago,  # SI, N|2: 01-09, 99
            "descFormaPago": desc_forma_pago,  # C/C, AN|10..100 - Solo si formaPagoFact = 99
            "valorCuotaPagada": total_factura,  # SI, N|1..11|1..2
        }]
        
        # Agregar referencia para NC/ND
        if self.hka_tipo_documento in ['04', '05', '06', '07'] and self.hka_documento_referencia:
            documento['datosTransaccion']['listaDocsFiscalReferenciados'] = [{
                "fechaEmisionDocFiscalReferenciado": self._get_hka_fecha_referencia() if self.hka_fecha_documento_referencia else "",
                "cufeFEReferenciada": self.hka_documento_referencia,  # Según swagger: cufeFEReferenciada (femenino)
                "nroFacturaPapel": "",  # Según swagger: nroFacturaPapel (no nroFacturaImpresora)
            }]
        
        return documento
    
    def action_send_hka(self):
        """Envía la factura a HKA"""
        self.ensure_one()
        
        if self.move_type not in ['out_invoice', 'out_refund']:
            raise UserError(_('Solo se pueden enviar facturas de venta.'))
        
        if self.state != 'posted':
            raise UserError(_('La factura debe estar validada para enviarla.'))
        
        if self.hka_cufe:
            raise UserError(_('Esta factura ya fue enviada a HKA.'))

        company = self.company_id or self.env.company
        company_ruc = _normalize_ruc(company.hka_ruc or company.vat)
        if not _is_valid_ruc(company_ruc):
            raise UserError(_("El RUC de la empresa no tiene formato válido para DGI. Use formato con guiones (ej: 155677155-2-2023)."))
        
        # Validar datos del cliente antes de enviar
        partner = self.partner_id
        if not partner:
            raise UserError(_('La factura debe tener un cliente asignado.'))
        
        # Validar RUC si es contribuyente
        tipo_cliente = partner.pa_tipo_cliente_fe or "02"
        if tipo_cliente == "01":  # Contribuyente
            ruc = partner.pa_ruc or partner.vat or ""
            ruc_limpio = ruc.replace("-", "").replace(" ", "").strip() if ruc else ""
            # RUC panameño tiene formato: 8-382-685 (7 dígitos) o similar
            # Validar que tenga al menos 7 dígitos
            if not ruc_limpio or len(ruc_limpio) < 7:
                raise UserError(_('El cliente contribuyente debe tener un RUC válido configurado (mínimo 7 dígitos).'))
        
        # Validar codigoUbicacion - CRÍTICO PARA CONTRIBUYENTES
        # El código debe estar registrado en HKA Factory y coincidir EXACTAMENTE
        # NO transformar, NO formatear - enviar tal cual del portal
        # Priorizar Many2one si existe, sino usar campo Char legacy
        if partner.pa_codigo_ubicacion_id:
            codigo_ubicacion = partner.pa_codigo_ubicacion_id.codigo
        else:
            codigo_ubicacion = partner.pa_codigo_ubicacion

        codigos_invalidos = ["0000", "01", "0101", "010101", "8-08-01", "080801", ""]

        if tipo_cliente == "01":  # Contribuyente
            if not codigo_ubicacion or codigo_ubicacion.strip() in codigos_invalidos:
                raise UserError(_(
                    '❌ Código de Ubicación HKA no configurado o inválido\n\n'
                    'El cliente contribuyente requiere un código de ubicación válido.\n\n'
                    'El código debe obtenerse del Portal HKA Factory:\n'
                    '1. Acceder a https://demo.thefactoryhka.com.pa\n'
                    '2. Ir a: Configuración → Datos Fiscales → Código de Ubicación\n'
                    '3. Copiar el código EXACTO (sin modificaciones)\n'
                    '4. Configurarlo en el campo "Código Ubicación" del contacto\n\n'
                    '⚠️ IMPORTANTE: El código debe coincidir EXACTAMENTE con el registrado en HKA.\n'
                    'No usar códigos genéricos de la DGI.'
                ))
        
        # Para Consumidor Final (02), el código es opcional pero recomendado
        elif codigo_ubicacion and codigo_ubicacion.strip() in codigos_invalidos:
            _logger.warning(
                f"Cliente {partner.name} (ID: {partner.id}) tiene código de ubicación inválido: {codigo_ubicacion}. "
                "El código no se enviará en el documento."
            )
        
        # Obtener cliente API
        client = self._get_hka_client()
        
        # Preparar documento
        documento = self._prepare_hka_documento()
        
        _logger.info(f"Enviando documento a HKA: {json.dumps(documento, indent=2)}")
        
        # Enviar a HKA
        result = client.enviar_documento(documento)
        
        # Crear registro de documento HKA
        hka_doc_vals = {
            'move_id': self.id,
            'company_id': self.company_id.id,
            'tipo_documento': self.hka_tipo_documento,
            'numero_documento': documento['datosTransaccion']['numeroDocumentoFiscal'],
            'fecha_emision': fields.Datetime.now(),
            'response_code': result.get('data', {}).get('codigo'),
            'response_message': result.get('data', {}).get('mensaje'),
            'response_json': json.dumps(result.get('data', {})),
        }
        
        if result.get('success'):
            data = result.get('data', {})
            
            # Convertir fechaRecepcionDGI de ISO 8601 a formato Odoo
            fecha_recepcion = None
            if data.get('fechaRecepcionDGI'):
                try:
                    # HKA devuelve formato ISO 8601: 2026-01-05T23:45:04-05:00
                    # Odoo espera formato: 2026-01-05 23:45:04
                    fecha_iso = data.get('fechaRecepcionDGI')
                    # Parsear ISO 8601 y convertir a formato Odoo
                    fecha_parsed = parser.parse(fecha_iso)
                    fecha_recepcion = fecha_parsed.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    _logger.warning(f"Error al parsear fechaRecepcionDGI: {e}")
            
            # Extraer QR de múltiples campos posibles (HKA puede devolver con diferentes nombres)
            qr_code = (
                data.get('qrCode') or  # camelCase (más común en APIs REST)
                data.get('qr_code') or  # snake_case
                data.get('qr') or  # minúsculas
                data.get('codigoQR') or  # español camelCase
                data.get('codigoQr') or  # español mixed
                data.get('qrCodeBase64') or  # si viene en base64
                None
            )
            
            hka_doc_vals.update({
                'cufe': data.get('cufe'),
                'qr_code': qr_code,
                'fecha_recepcion_dgi': fecha_recepcion,
                'numero_protocolo': data.get('nroProtocoloAutorizacion'),
                'state': 'authorized',
            })
            
            # Log para debug si no se encontró QR
            if not qr_code:
                _logger.warning(
                    f"QR no encontrado en respuesta HKA. "
                    f"Campos disponibles: {list(data.keys())}. "
                    f"Respuesta completa: {json.dumps(data, indent=2)[:500]}"
                )
            
            hka_doc = self.env['hka.document'].create(hka_doc_vals)
            self.hka_document_id = hka_doc.id

            # Descargar PDF de HKA con reintentos (puede no estar listo al instante)
            pdf_result = hka_doc._download_pdf_with_retry(max_attempts=3, delay_seconds=2)
            if pdf_result and isinstance(pdf_result, dict):
                _logger.warning(
                    'No se pudo descargar el PDF de HKA tras el CUFE: %s',
                    pdf_result.get('params', {}).get('message', '')
                )

            # Solo mostrar notificación / abrir PDF si no es envío automático
            if not self.env.context.get('skip_notification'):
                if hka_doc.pdf_file and hka_doc.pdf_filename:
                    # Misma URL que action_download_pdf para forzar descarga
                    base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '').rstrip('/')
                    url = f'{base_url}/web/content/{hka_doc._name}/{hka_doc.id}/pdf_file/{hka_doc.pdf_filename}?download=true'
                    return {
                        'type': 'ir.actions.act_url',
                        'url': url,
                        'target': 'self',
                    }
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Factura Electrónica Enviada'),
                        'message': _('CUFE: %s') % data.get('cufe'),
                        'type': 'success',
                        'sticky': True,
                    }
                }
            else:
                # En envío automático, solo registrar en chatter
                self.message_post(
                    body=_("✅ <b>Factura enviada automáticamente a HKA</b><br/>"
                          "CUFE: <b>%s</b><br/>"
                          "Estado: <b>Autorizado</b>") % data.get('cufe'),
                    subject=_("Facturación Electrónica Automática")
                )
        else:
            hka_doc_vals['state'] = 'rejected'
            hka_doc = self.env['hka.document'].create(hka_doc_vals)
            self.hka_document_id = hka_doc.id

            error_msg = result.get('error', 'Error desconocido')
            # En envío automático, no lanzar excepción, solo registrar
            if self.env.context.get('skip_notification'):
                raise Exception(error_msg)  # Para que el _post lo capture
            else:
                raise UserError(_('Error al enviar a HKA: %s') % error_msg)
    
    def action_cancel_dgi(self):
        """Anula la factura en la DGI vía API HKA."""
        for move in self:
            if move.move_type not in ('out_invoice', 'out_refund'):
                raise UserError(_('Solo se pueden anular facturas o notas de crédito/débito de venta.'))
            if move.state != 'posted':
                raise UserError(_('El documento debe estar validado para anularlo en DGI.'))
            if not move.hka_cufe:
                raise UserError(_('La factura no tiene CUFE y no puede anularse.'))
            if move.hka_estado_dgi != 'autorizado':
                raise UserError(_('Solo se pueden anular facturas autorizadas por la DGI.'))
            # No anular si ya existe nota de crédito que referencia esta factura (solo para facturas)
            if move.move_type == 'out_invoice':
                if 'reversal_move_id' in self.env['account.move']._fields:
                    nc = self.env['account.move'].search_count([
                        ('reversal_move_id', '=', move.id),
                        ('state', '!=', 'cancel'),
                    ])
                else:
                    nc = self.env['account.move'].search_count([
                        ('move_type', '=', 'out_refund'),
                        ('hka_documento_referencia', '=', move.hka_cufe),
                        ('state', '!=', 'cancel'),
                    ])
                if nc:
                    raise UserError(_('La factura tiene nota de crédito asociada. No se puede anular en DGI.'))

            client = move._get_hka_client()
            result = client.anular_documento(
                move.hka_cufe,
                move.hka_motivo_anulacion or _('Anulación desde ERP'),
            )
            data = result.get('data') or result
            codigo = data.get('Codigo') or data.get('codigo')
            if codigo != '200':
                raise UserError(_('Error anulando en DGI: %s') % (data.get('Mensaje') or data.get('mensaje') or result.get('error', '')))

            if move.hka_document_id:
                move.hka_document_id.write({'state': 'cancelled'})
            move.message_post(
                body=_('Factura anulada en DGI correctamente.'),
                subject=_('Anulación DGI'),
            )
        return True

    def action_cancel_hka(self):
        """Abre wizard para indicar motivo y luego anular en DGI."""
        self.ensure_one()
        return {
            'name': _('Anular en DGI'),
            'type': 'ir.actions.act_window',
            'res_model': 'hka.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.id,
                'default_motivo_anulacion': self.hka_motivo_anulacion or '',
            },
        }
    
    def action_view_hka_document(self):
        """Abre el documento HKA relacionado"""
        self.ensure_one()
        if self.hka_document_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'hka.document',
                'res_id': self.hka_document_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_invoice_sent(self):
        """Al enviar factura por correo, usar PDF de HKA si existe (mismo que Reimprimir factura fiscal)."""
        self.ensure_one()
        if self.hka_cufe and self.hka_document_id and self.hka_document_id.pdf_file:
            # Asegurar que el adjunto del wizard sea el PDF oficial de HKA
            Attachment = self.env['ir.attachment'].sudo()
            domain = [
                ('res_model', '=', 'account.move'),
                ('res_id', '=', self.id),
                ('res_field', '=', 'invoice_pdf_report_file'),
            ]
            att = Attachment.search(domain, limit=1)
            name = self.hka_document_id.pdf_filename or f'Factura_Fiscal_{self.name or self.id}.pdf'
            vals = {
                'name': name,
                'res_model': 'account.move',
                'res_id': self.id,
                'res_field': 'invoice_pdf_report_file',
                'datas': self.hka_document_id.pdf_file,
                'type': 'binary',
            }
            if att:
                att.write(vals)
            else:
                Attachment.create(vals)
            self.invalidate_recordset(fnames=['invoice_pdf_report_id', 'invoice_pdf_report_file'])
        return super().action_invoice_sent()

    def _post(self, soft=True):
        """Sobrescribe _post para enviar automáticamente a HKA si está configurado"""
        posted = super()._post(soft=soft)
        
        # Filtrar facturas que deben enviarse automáticamente
        invoices_to_send = posted.filtered(
            lambda m: m.move_type in ['out_invoice', 'out_refund']
            and m.company_id.hka_auto_send
            and not m.hka_cufe
            and m.state == 'posted'
        )
        
        # Enviar automáticamente cada factura
        for invoice in invoices_to_send:
            try:
                # Llamar al método de envío sin mostrar notificación
                # para evitar interrupciones en el flujo
                invoice.with_context(skip_notification=True).action_send_hka()
                _logger.info(f"Factura {invoice.name} enviada automáticamente a HKA")
            except UserError as e:
                # Si es un error de usuario (configuración, etc.), registrar pero no bloquear
                _logger.warning(f"Error al enviar factura {invoice.name} a HKA: {e}")
                invoice.message_post(
                    body=_("⚠️ <b>Error al enviar automáticamente a HKA:</b><br/>%s<br/><br/>"
                          "Puede intentar enviar manualmente usando el botón 'Enviar a DGI'.") % str(e),
                    subject=_("Error Facturación Electrónica Automática")
                )
            except Exception as e:
                # Cualquier otro error, registrar en log y chatter
                _logger.error(f"Error inesperado al enviar factura {invoice.name} a HKA: {e}", exc_info=True)
                invoice.message_post(
                    body=_("⚠️ <b>Error inesperado al enviar automáticamente a HKA:</b><br/>%s<br/><br/>"
                          "Puede intentar enviar manualmente usando el botón 'Enviar a DGI'.") % str(e),
                    subject=_("Error Facturación Electrónica Automática")
                )
        
        return posted






