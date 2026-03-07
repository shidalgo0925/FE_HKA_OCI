# ETS Facturación Electrónica Panamá - HKA

Módulo de **Odoo 18** para emitir facturas electrónicas en Panamá integrado con **The Factory HKA Corp** (proveedor autorizado ante la DGI).

| | |
|---|---|
| **Autor** | Easytech Services |
| **Web** | https://easytech.services |
| **Repositorio** | https://github.com/shidalgo0925/FE_HKA_OCI |
| **Licencia** | LGPL-3 |
| **Versión** | 18.0.1.1.0 |
| **Última actualización** | Marzo 2026 |

---

## ¿Qué hace este módulo?

- Conecta Odoo con la API de HKA para enviar facturas y notas de crédito/débito a la **DGI (Dirección General de Ingresos)**.
- Obtiene el **CUFE** (Código Único de Factura Electrónica), descarga el **XML y PDF** autorizados y permite **anular** documentos ya autorizados desde Odoo.
- Gestiona **códigos de ubicación** de Panamá (provincia, distrito, corregimiento), **CPBS** y validación de **RUC** para contribuyentes.

## Características

- **Configuración:** Credenciales HKA por compañía (demo/producción), envío automático opcional al validar.
- **Envío a DGI:** Botón *Enviar a DGI* en facturas y notas de crédito/débito validadas.
- **Anulación:** Botón *Anular en DGI* → wizard para indicar motivo → solo si la factura está autorizada y no tiene nota de crédito asociada.
- **Documentos:** Historial en *Facturación Electrónica → Documentos Electrónicos* (CUFE, estado, PDF).
- **Ubicaciones:** Carga desde CSV (`data/hka_ubicaciones.csv`) según catálogo DGI/HKA; una sola fuente para evitar errores de código.
- **Contactos:** Tipo de cliente (contribuyente/consumidor final), RUC y código de ubicación para FE.

## Requisitos

- **Odoo:** 18.0
- **Python:** `requests`, `PyJWT`
- **HKA:** Cuenta activa en The Factory HKA, licencia de facturación electrónica vigente; certificado digital para producción.

## Instalación

1. Añadir la carpeta `FE_HKA_OCI` a la ruta de addons de Odoo.
2. Reiniciar Odoo (o actualizar lista de aplicaciones).
3. En **Apps**, buscar *ETS Facturación Electrónica Panamá* e **Instalar**.

## Uso rápido

- **Enviar una factura:** Validar la factura → botón *Enviar a DGI*. Si está activo el envío automático, se envía al validar.
- **Anular en DGI:** Solo para facturas ya autorizadas. Botón *Anular en DGI* → escribir motivo (opcional) → *Confirmar*.
- **Reimprimir PDF fiscal:** Botón *Reimprimir factura fiscal* una vez enviada.

## Estructura del repositorio

- `models/` — account_move, hka_api, hka_document (envío, anulación, descarga).
- `wizard/` — wizard de anulación en DGI (motivo + confirmar).
- `data/` — carga de ubicaciones Panamá (CSV), secuencias, CPBS, etc.
- `views/` — formularios y botones de factura, documentos FE, contactos, configuración.

## Dónde encontrarnos

- **Soporte y contacto:** [Easytech Services](https://easytech.services)
- **Código fuente:** [GitHub – FE_HKA_OCI](https://github.com/shidalgo0925/FE_HKA_OCI)
- **Odoo 18** · Facturación electrónica Panamá · The Factory HKA · DGI

---

Desarrollado por **Easytech Services** · https://easytech.services
