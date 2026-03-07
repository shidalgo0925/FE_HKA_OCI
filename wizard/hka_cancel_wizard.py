# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HKACancelWizard(models.TransientModel):
    _name = 'hka.cancel.wizard'
    _description = 'Anular documento en DGI'

    move_id = fields.Many2one('account.move', string='Factura', required=True, readonly=True)
    motivo_anulacion = fields.Text(
        string='Motivo de anulación',
        help='Motivo que se enviará a la DGI para la anulación del documento.',
    )

    def action_confirm(self):
        """Escribe el motivo en la factura y ejecuta la anulación en DGI."""
        self.ensure_one()
        if not self.move_id:
            raise UserError(_('No hay factura asociada.'))
        self.move_id.hka_motivo_anulacion = self.motivo_anulacion or False
        self.move_id.action_cancel_dgi()
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
