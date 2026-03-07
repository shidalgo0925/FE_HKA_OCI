# -*- coding: utf-8 -*-
"""
HKA Factory API Client
Integración con The Factory HKA para Facturación Electrónica de Panamá
"""

import logging
import requests
import json
from datetime import datetime, timedelta, timezone

_logger = logging.getLogger(__name__)


class HKAApiClient:
    """Cliente para la API de HKA Factory"""
    
    # URLs de los ambientes
    URLS = {
        'demo': 'https://demointegracion.thefactoryhka.com.pa',
        'production': 'https://integracion.thefactoryhka.com.pa',
    }
    
    def __init__(self, usuario, clave, ambiente='demo'):
        """
        Inicializa el cliente de la API
        
        Args:
            usuario: Usuario de integración HKA
            clave: Clave del usuario
            ambiente: 'demo' o 'production'
        """
        self.usuario = usuario
        self.clave = clave
        self.ambiente = ambiente
        self.base_url = self.URLS.get(ambiente, self.URLS['demo'])
        self.token = None
        self.token_expiration = None
    
    def _get_headers(self, with_auth=True):
        """Obtiene los headers para las peticiones"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if with_auth and self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers
    
    def authenticate(self):
        """
        Autentica con la API y obtiene el token JWT
        
        Returns:
            dict: Respuesta de autenticación con token
        """
        url = f"{self.base_url}/api/Autenticacion"
        payload = {
            "usuario": self.usuario,
            "clave": self.clave
        }
        
        try:
            _logger.info(f"HKA API: Autenticando con {url}")
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(with_auth=False),
                timeout=30
            )
            
            data = response.json()
            
            if data.get('codigo') == '200':
                self.token = data.get('token')
                # Parsear expiración
                exp_str = data.get('expiracion', '')
                if exp_str:
                    try:
                        self.token_expiration = datetime.fromisoformat(
                            exp_str.replace('Z', '+00:00')
                        )
                    except Exception:
                        # Token válido por 24 horas por defecto
                        self.token_expiration = datetime.now(timezone.utc) + timedelta(hours=24)
                
                _logger.info("HKA API: Autenticación exitosa")
                return {'success': True, 'data': data}
            else:
                _logger.error(f"HKA API: Error de autenticación - {data.get('mensaje')}")
                return {'success': False, 'error': data.get('mensaje')}
                
        except requests.exceptions.Timeout:
            _logger.error("HKA API: Timeout en autenticación")
            return {'success': False, 'error': 'Timeout al conectar con HKA'}
        except requests.exceptions.RequestException as e:
            _logger.error(f"HKA API: Error de conexión - {e}")
            return {'success': False, 'error': f'Error de conexión: {str(e)}'}
        except Exception as e:
            _logger.error(f"HKA API: Error inesperado - {e}")
            return {'success': False, 'error': f'Error inesperado: {str(e)}'}
    
    def _ensure_authenticated(self):
        """Asegura que hay un token válido"""
        now_utc = datetime.now(timezone.utc)
        if not self.token or (self.token_expiration and now_utc >= self.token_expiration):
            result = self.authenticate()
            if not result.get('success'):
                raise Exception(result.get('error', 'Error de autenticación'))
    
    def enviar_documento(self, documento):
        """
        Envía un documento electrónico
        
        Args:
            documento: dict con la estructura DocumentoElectronico
            
        Returns:
            dict: Respuesta con CUFE, QR, etc.
        """
        self._ensure_authenticated()
        
        url = f"{self.base_url}/api/Enviar"
        payload = {"documento": documento}
        
        try:
            # Verificación según documentación oficial HKA (método Enviar)
            # unidadMedida: Tipo String, Requerido NO, Formato AN|1..20
            # Debe corresponder al catálogo de unidades de medida Tabla 3 (Tabla 29 DGI)
            # IMPORTANTE: Campo es OPCIONAL según documentación oficial
            # Solo validar/corregir si el campo está presente
            import json as json_lib
            
            # Validar unidadMedida solo si está presente (campo es opcional)
            if 'documento' in payload and 'listaItems' in payload['documento']:
                for idx, item in enumerate(payload['documento']['listaItems']):
                    tipo_item = item.get('tipoItem', 'N/A')
                    
                    # Si unidadMedida está presente, validar que sea válido
                    if 'unidadMedida' in item:
                        unidad_medida = item.get('unidadMedida', '')
                        # Validar longitud (1-20 caracteres según documentación)
                        if unidad_medida and (len(str(unidad_medida)) < 1 or len(str(unidad_medida)) > 20):
                            _logger.warning(f"HKA API: Item {idx+1}: unidadMedida='{unidad_medida}' longitud inválida, eliminando")
                            # Eliminar si es inválido (campo es opcional)
                            del item['unidadMedida']
                        elif not unidad_medida or unidad_medida.strip() == '':
                            # Eliminar si está vacío (campo es opcional)
                            _logger.info(f"HKA API: Item {idx+1}: unidadMedida vacío, eliminando (campo opcional)")
                            del item['unidadMedida']
                        else:
                            _logger.info(f"HKA API: Item {idx+1}: tipoItem={tipo_item}, unidadMedida='{unidad_medida}' ✅")
                    else:
                        # Campo no presente - esto es válido según documentación (opcional)
                        _logger.info(f"HKA API: Item {idx+1}: tipoItem={tipo_item}, unidadMedida NO presente (opcional) ✅")
            
            payload_str = json_lib.dumps(payload, ensure_ascii=False)
            _logger.info(f"HKA API: Enviando documento a {url}")
            _logger.info(f"HKA API: Payload completo (primeros 2000 chars):\n{payload_str[:2000]}")
            
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=60
            )
            
            data = response.json()
            
            if data.get('codigo') == '200':
                _logger.info(f"HKA API: Documento enviado - CUFE: {data.get('cufe')}")
                return {'success': True, 'data': data}
            else:
                _logger.error(f"HKA API: Error al enviar - {data.get('mensaje')}")
                return {'success': False, 'error': data.get('mensaje'), 'data': data}
                
        except Exception as e:
            _logger.error(f"HKA API: Error al enviar documento - {e}")
            return {'success': False, 'error': str(e)}
    
    def anular_documento(self, cufe, motivo_anulacion):
        """
        Anula un documento electrónico (REST con CUFE).
        Wiki HKA documenta AnulacionDocumento con datosDocumento; si este endpoint falla,
        puede ser necesario usar payload con numeroDocumentoFiscal, puntoFacturacionFiscal, etc.

        Args:
            cufe: CUFE del documento a anular
            motivo_anulacion: Motivo de la anulación

        Returns:
            dict: {'success': bool, 'data': {...}, 'error': str opcional}
        """
        self._ensure_authenticated()

        url = f"{self.base_url}/api/Anulacion"
        payload = {
            "cufe": cufe,
            "motivoAnulacion": motivo_anulacion
        }
        
        try:
            _logger.info(f"HKA API: Anulando documento {cufe}")
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=30
            )
            
            data = response.json()
            codigo = data.get('Codigo') or data.get('codigo')
            mensaje = data.get('Mensaje') or data.get('mensaje')
            if codigo == '200':
                _logger.info(f"HKA API: Documento anulado - {cufe}")
                return {'success': True, 'data': data}
            else:
                _logger.error(f"HKA API: Error al anular - {mensaje}")
                return {'success': False, 'error': mensaje, 'data': data}
                
        except Exception as e:
            _logger.error(f"HKA API: Error al anular documento - {e}")
            return {'success': False, 'error': str(e)}
    
    def consultar_estado(self, cufe):
        """
        Consulta el estado de un documento
        
        Args:
            cufe: CUFE del documento
            
        Returns:
            dict: Estado del documento
        """
        self._ensure_authenticated()
        
        url = f"{self.base_url}/api/EstadoDocumento"
        payload = {"cufe": cufe}
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=30
            )
            
            data = response.json()
            return {'success': data.get('codigo') == '200', 'data': data}
                
        except Exception as e:
            _logger.error(f"HKA API: Error al consultar estado - {e}")
            return {'success': False, 'error': str(e)}
    
    def descargar_documento(self, cufe, tipo='pdf'):
        """
        Descarga un documento en XML o PDF
        
        Args:
            cufe: CUFE del documento
            tipo: 'pdf' o 'xml'
            
        Returns:
            dict: Documento en base64
        """
        self._ensure_authenticated()
        
        url = f"{self.base_url}/api/Descarga"
        payload = {
            "cufe": cufe,
            "tipoArchivo": tipo.upper()
        }
        
        try:
            _logger.info(f"HKA API: Descargando documento {cufe} tipo {tipo}")
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=60
            )
            
            data = response.json()
            codigo = data.get('codigo') or data.get('Codigo')
            _logger.info(f"HKA API: Respuesta descarga - código: {codigo}, keys: {list(data.keys())}")
            # HKA puede devolver 200 o 0 como éxito (0 con mensaje "Se ha descargado existosamente el archivo")
            if codigo in ('200', 200, '0', 0):
                return {'success': True, 'data': data}
            error_msg = data.get('mensaje') or data.get('Mensaje', 'Error desconocido al descargar')
            _logger.error(f"HKA API: Error al descargar - {error_msg}")
            return {'success': False, 'error': error_msg, 'data': data}
                
        except Exception as e:
            _logger.error(f"HKA API: Error al descargar documento - {e}")
            return {'success': False, 'error': str(e)}
    
    def consultar_folios(self):
        """
        Consulta los folios restantes
        
        Returns:
            dict: Información de folios
        """
        self._ensure_authenticated()
        
        url = f"{self.base_url}/api/FoliosRestantes"
        
        try:
            response = requests.post(
                url,
                json={},
                headers=self._get_headers(),
                timeout=30
            )
            
            data = response.json()
            return {'success': data.get('codigo') == '200', 'data': data}
                
        except Exception as e:
            _logger.error(f"HKA API: Error al consultar folios - {e}")
            return {'success': False, 'error': str(e)}
