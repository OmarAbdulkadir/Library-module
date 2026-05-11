from odoo import models, fields, api
from datetime import date

class LibraryMember(models.Model):
    _name = 'library.member'
    _description = 'Library Member'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Full Name', required=True, tracking=True)
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    student_id = fields.Char(string='Student ID')
    membership_date = fields.Date(string='Member Since', default=fields.Date.today)
    borrow_ids = fields.One2many('library.borrow', 'member_id', string='Borrow History')
    active_borrows = fields.Integer(string='Active Borrows', compute='_compute_active_borrows')
    total_borrows = fields.Integer(string='Total Books Borrowed', compute='_compute_total_borrows')
    borrow_limit = fields.Integer(string='Borrow Limit', default=3)
    streak = fields.Integer(string='Borrow Streak', compute='_compute_streak')
    room_booking_ids = fields.One2many('library.room.booking', 'member_id', string='Room Bookings')
    state = fields.Selection([
        ('active', 'Active'),
        ('suspended', 'Suspended'),
    ], string='Status', default='active', tracking=True)
    reservation_ids = fields.One2many('library.reservation', 'member_id', string='Reservations')
    has_overdue = fields.Boolean(string='Has Overdue Books', compute='_compute_has_overdue', store=True)

    @api.depends('borrow_ids', 'borrow_ids.state')
    def _compute_active_borrows(self):
        for member in self:
            member.active_borrows = len(member.borrow_ids.filtered(lambda b: b.state == 'borrowed'))

    @api.depends('borrow_ids')
    def _compute_total_borrows(self):
        for member in self:
            member.total_borrows = len(member.borrow_ids)

    @api.depends('borrow_ids')
    def _compute_streak(self):
        for member in self:
            member.streak = len(member.borrow_ids.filtered(lambda b: b.state == 'returned'))

    @api.depends('borrow_ids', 'borrow_ids.is_overdue')
    def _compute_has_overdue(self):
        for member in self:
            member.has_overdue = any(b.is_overdue for b in member.borrow_ids)

    def action_suspend(self):
        self.state = 'suspended'

    def action_activate(self):
        self.state = 'active'

    def _cron_auto_suspend_overdue(self):
        today = fields.Date.today()
        members = self.search([('state', '=', 'active')])
        for member in members:
            overdue_borrows = member.borrow_ids.filtered(
                lambda b: b.state == 'borrowed' and b.due_date and
                (today - b.due_date).days > 7
            )
            if overdue_borrows:
                member.state = 'suspended'
                member.message_post(body='Auto suspended due to overdue books for more than 7 days.')
