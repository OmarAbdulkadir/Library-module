from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    library_enable_borrowing = fields.Boolean(
        string='Enable Borrowing System',
        config_parameter='library.enable_borrowing',
    )
    library_enable_ebooks = fields.Boolean(
        string='Enable E-Books',
        config_parameter='library.enable_ebooks',
    )
    library_warning_message = fields.Char(
        string='Announcement Message',
        config_parameter='library.warning_message',
    )
    library_show_warning = fields.Boolean(
        string='Show Announcement Banner',
        config_parameter='library.show_warning',
    )

    def get_values(self):
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()
        res['library_enable_borrowing'] = params.get_param('library.enable_borrowing', 'True') == 'True'
        res['library_enable_ebooks'] = params.get_param('library.enable_ebooks', 'True') == 'True'
        res['library_show_warning'] = params.get_param('library.show_warning', 'False') == 'True'
        return res

    def set_values(self):
        super().set_values()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('library.enable_borrowing', str(self.library_enable_borrowing))
        params.set_param('library.enable_ebooks', str(self.library_enable_ebooks))
        params.set_param('library.show_warning', str(self.library_show_warning))

        # Hide/show borrowings menu
        self.env.cr.execute(
            "UPDATE ir_ui_menu SET active = %s WHERE id = 141",
            (self.library_enable_borrowing,)
        )
        self.env['ir.ui.menu'].clear_caches()

        # Apply ebook filter to books action
        action = self.env.ref('library.action_library_book')
        if not self.library_enable_ebooks:
            action.domain = [('book_type', '=', 'physical')]
        else:
            action.domain = []
