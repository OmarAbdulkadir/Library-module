from odoo import models, fields, api
from odoo.exceptions import ValidationError

class LibraryReservation(models.Model):
    _name = 'library.reservation'
    _description = 'Book Reservation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    member_id = fields.Many2one('library.member', string='Member', required=True, tracking=True)
    book_id = fields.Many2one('library.book', string='Book', required=True, tracking=True)
    reservation_date = fields.Date(string='Reserved On', default=fields.Date.today)
    expiry_date = fields.Date(string='Expires On', compute='_compute_expiry', store=True)
    state = fields.Selection([
        ('waiting', 'Waiting'),
        ('notified', 'Notified - Book Available'),
        ('fulfilled', 'Fulfilled'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ], string='Status', default='waiting', tracking=True)
    notes = fields.Text(string='Notes')

    @api.depends('member_id', 'book_id')
    def _compute_name(self):
        for rec in self:
            if rec.member_id and rec.book_id:
                rec.name = f"Reservation: {rec.member_id.name} - {rec.book_id.name}"
            else:
                rec.name = 'New Reservation'

    @api.depends('reservation_date')
    def _compute_expiry(self):
        from datetime import timedelta
        for rec in self:
            if rec.reservation_date:
                rec.expiry_date = rec.reservation_date + timedelta(days=7)

    @api.constrains('member_id', 'book_id')
    def _check_duplicate(self):
        for rec in self:
            existing = self.search([
                ('member_id', '=', rec.member_id.id),
                ('book_id', '=', rec.book_id.id),
                ('state', 'in', ['waiting', 'notified']),
                ('id', '!=', rec.id),
            ])
            if existing:
                raise ValidationError(f"You already have an active reservation for '{rec.book_id.name}'!")

    def action_cancel(self):
        self.state = 'cancelled'

    def action_fulfilled(self):
        self.state = 'fulfilled'

    def _notify_available(self):
        template = self.env.ref('library.email_template_book_available', raise_if_not_found=False)
        for rec in self:
            rec.state = 'notified'
            rec.message_post(body=f"Good news! '{rec.book_id.name}' is now available. Please borrow it within 7 days.")
            if template and rec.member_id.email:
                template.send_mail(rec.id, force_send=True)

    def _cron_check_expired(self):
        today = fields.Date.today()
        expired = self.search([
            ('state', 'in', ['waiting', 'notified']),
            ('expiry_date', '<', today),
        ])
        expired.write({'state': 'expired'})

    @api.model
    def _check_reservations_for_book(self, book_id):
        reservations = self.search([
            ('book_id', '=', book_id),
            ('state', '=', 'waiting'),
        ], order='create_date asc', limit=1)
        if reservations:
            reservations._notify_available()
