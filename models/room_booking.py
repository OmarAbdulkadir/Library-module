from odoo import models, fields, api
from odoo.exceptions import ValidationError
import qrcode
import base64
from io import BytesIO

class LibraryRoomBooking(models.Model):
    _name = 'library.room.booking'
    _description = 'Room Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    member_id = fields.Many2one('library.member', string='Member', required=True, tracking=True)
    room_id = fields.Many2one('library.room', string='Room', required=True, tracking=True)
    start_time = fields.Datetime(string='Start Time', required=True)
    end_time = fields.Datetime(string='End Time', required=True)
    duration_hours = fields.Float(string='Duration (Hours)', compute='_compute_duration')
    needs_computer = fields.Boolean(string='Needs Computer', default=False)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending', tracking=True)
    notes = fields.Text(string='Notes')
    rejection_reason = fields.Text(string='Rejection Reason')
    qr_code = fields.Binary(string='QR Code', attachment=True)
    qr_code_text = fields.Char(string='QR Code Data', compute='_compute_qr_text')

    @api.depends('member_id', 'room_id', 'start_time')
    def _compute_name(self):
        for rec in self:
            if rec.member_id and rec.room_id:
                rec.name = f"{rec.member_id.name} - {rec.room_id.name}"
            else:
                rec.name = 'New Booking'

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for rec in self:
            if rec.start_time and rec.end_time:
                delta = rec.end_time - rec.start_time
                rec.duration_hours = delta.total_seconds() / 3600
            else:
                rec.duration_hours = 0

    @api.depends('member_id', 'room_id')
    def _compute_qr_text(self):
        for rec in self:
            if rec.id:
                rec.qr_code_text = f"LIBRARY-BOOKING-{rec.id}-MEMBER-{rec.member_id.id}-ROOM-{rec.room_id.id}"
            else:
                rec.qr_code_text = ''

    @api.constrains('start_time', 'end_time', 'member_id', 'room_id')
    def _check_booking(self):
        for rec in self:
            if rec.duration_hours > 2:
                raise ValidationError('Maximum booking duration is 2 hours!')
            if rec.start_time and rec.start_time < fields.Datetime.now():
                raise ValidationError('Cannot book a room in the past!')
            if rec.start_time and rec.end_time and rec.end_time <= rec.start_time:
                raise ValidationError('End time must be after start time!')
            overlap = self.search([
                ('room_id', '=', rec.room_id.id),
                ('state', 'in', ['approved', 'active']),
                ('id', '!=', rec.id),
                ('start_time', '<', rec.end_time),
                ('end_time', '>', rec.start_time),
            ])
            if overlap:
                raise ValidationError(f"Room '{rec.room_id.name}' is already booked during this time!")

    def _generate_qr(self):
        for rec in self:
            qr_data = f"LIBRARY-BOOKING-{rec.id}-MEMBER-{rec.member_id.id}-ROOM-{rec.room_id.id}"
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            rec.qr_code = base64.b64encode(buffer.getvalue())

    def action_approve(self):
        self.state = 'approved'
        self._generate_qr()
        self.message_post(body="Booking approved. QR code generated.")

    def action_reject(self):
        self.state = 'rejected'
        self.message_post(body=f"Booking rejected. Reason: {self.rejection_reason or 'No reason given'}")

    def action_checkin(self):
        self.state = 'active'
        self.message_post(body="Member checked in.")

    def action_checkout(self):
        self.state = 'done'
        self.message_post(body="Member checked out. Booking complete.")

    def action_cancel(self):
        self.state = 'cancelled'
        self.message_post(body="Booking cancelled.")
