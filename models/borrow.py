from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta

class LibraryBorrow(models.Model):
    _name = 'library.borrow'
    _description = 'Book Borrowing'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    member_id = fields.Many2one('library.member', string='Member', required=True, tracking=True)
    book_id = fields.Many2one('library.book', string='Book', required=True, tracking=True)
    borrow_date = fields.Date(string='Borrow Date', default=fields.Date.today, required=True)
    due_date = fields.Date(string='Due Date')
    return_date = fields.Date(string='Return Date')
    duration_days = fields.Integer(string='Duration (Days)', compute='_compute_duration')
    state = fields.Selection([
        ('pending', 'Pending Approval'),
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending', tracking=True)
    is_overdue = fields.Boolean(string='Is Overdue', compute='_compute_overdue', store=True)
    fine_amount = fields.Float(string='Fine Amount', compute='_compute_fine', store=True)
    rejection_reason = fields.Text(string='Rejection Reason')
    notes = fields.Text(string='Notes')

    @api.depends('member_id', 'book_id', 'borrow_date')
    def _compute_name(self):
        for rec in self:
            if rec.member_id and rec.book_id:
                rec.name = f"{rec.member_id.name} - {rec.book_id.name}"
            else:
                rec.name = 'New Borrow'

    @api.depends('borrow_date', 'return_date', 'due_date')
    def _compute_duration(self):
        for rec in self:
            if rec.borrow_date and rec.return_date:
                rec.duration_days = (rec.return_date - rec.borrow_date).days
            elif rec.borrow_date and rec.due_date:
                rec.duration_days = (rec.due_date - rec.borrow_date).days
            else:
                rec.duration_days = 0

    @api.depends('due_date', 'state', 'return_date')
    def _compute_overdue(self):
        today = fields.Date.today()
        for rec in self:
            if rec.state == 'returned':
                rec.is_overdue = False
            elif rec.state == 'borrowed' and rec.due_date and rec.due_date < today:
                rec.is_overdue = True
            else:
                rec.is_overdue = False

    @api.depends('is_overdue', 'due_date', 'state', 'return_date')
    def _compute_fine(self):
        today = fields.Date.today()
        for rec in self:
            if rec.state == 'returned':
                rec.fine_amount = 0.0
            elif rec.is_overdue and rec.due_date:
                days_overdue = (today - rec.due_date).days
                rec.fine_amount = days_overdue * 0.5
            else:
                rec.fine_amount = 0.0

    def action_approve(self):
        for rec in self:
            # Check borrow limit
            active = self.search_count([
                ('member_id', '=', rec.member_id.id),
                ('state', '=', 'borrowed'),
                ('id', '!=', rec.id)
            ])
            if active >= rec.member_id.borrow_limit:
                raise ValidationError(
                    f"{rec.member_id.name} has reached their borrow limit of {rec.member_id.borrow_limit} books!"
                )
            # Check available copies
            if rec.book_id.book_type == 'physical' and rec.book_id.available_copies <= 0:
                raise ValidationError(f"No copies of '{rec.book_id.name}' are available!")
            # Set due date to 14 days from today
            rec.write({
                'state': 'borrowed',
                'borrow_date': fields.Date.today(),
                'due_date': fields.Date.today() + timedelta(days=14),
            })
            rec.message_post(body=f"Borrow request approved. Due date: {rec.due_date}")

    def action_reject(self):
        for rec in self:
            rec.write({'state': 'rejected'})
            rec.message_post(body=f"Borrow request rejected.")

    def action_return(self):
        for rec in self:
            rec.write({
                'state': 'returned',
                'return_date': fields.Date.today(),
                'is_overdue': False,
                'fine_amount': 0.0,
            })
            self.env['library.reservation']._check_reservations_for_book(rec.book_id.id)

    def action_renew(self):
        for rec in self:
            if rec.state != 'borrowed':
                raise ValidationError('Can only renew active borrows!')
            rec.due_date = rec.due_date + timedelta(days=7)
            rec.message_post(body=f"Borrow renewed. New due date: {rec.due_date}")

    def action_pay_fine(self):
        for rec in self:
            rec.fine_amount = 0.0
            rec.message_post(body="Fine paid and cleared.")
