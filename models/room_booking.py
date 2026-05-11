from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import qrcode
import base64
from io import BytesIO

TIME_SLOTS = [
    ('08:30', '08:30 - 10:30'),
    ('10:30', '10:30 - 12:30'),
    ('12:30', '12:30 - 14:30'),
    ('14:30', '14:30 - 16:30'),
    ('16:30', '16:30 - 18:30'),
    ('18:30', '18:30 - 20:30'),
    ('20:30', '20:30 - 22:30'),
]

class LibraryRoomBooking(models.Model):
    _name = 'library.room.booking'
    _description = 'Room Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    member_id = fields.Many2one('library.member', string='Member', required=True, tracking=True)
    room_id = fields.Many2one('library.room', string='Room', required=True, tracking=True)
    booking_date = fields.Date(string='Date', required=True, default=fields.Date.today)
    time_slot = fields.Selection(TIME_SLOTS, string='Time Slot', required=True)
    start_time = fields.Datetime(string='Start Time', compute='_compute_times', store=True)
    end_time = fields.Datetime(string='End Time', compute='_compute_times', store=True)
    duration_hours = fields.Float(string='Duration (Hours)', default=2.0)
    group_size = fields.Integer(string='Group Size', required=True, default=3)
    needs_computer = fields.Boolean(string='Needs Computer', default=False)
    language = fields.Selection([
        ('en', 'English'),
        ('tr', 'Türkçe'),
    ], string='Language', default='en')
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
    qr_code_text = fields.Char(string='QR Code Data')
    auto_cancel_time = fields.Datetime(string='Auto Cancel At', compute='_compute_auto_cancel', store=True)
    completed_at = fields.Datetime(string='Completed At')

    @api.depends('member_id', 'room_id', 'booking_date', 'time_slot')
    def _compute_name(self):
        for rec in self:
            if rec.member_id and rec.room_id and rec.time_slot:
                slot_label = dict(TIME_SLOTS).get(rec.time_slot, '')
                rec.name = f"{rec.member_id.name} - {rec.room_id.name} - {slot_label}"
            else:
                rec.name = 'New Booking'

    @api.depends('booking_date', 'time_slot')
    def _compute_times(self):
        for rec in self:
            if rec.booking_date and rec.time_slot:
                hour = int(rec.time_slot.split(':')[0])
                minute = int(rec.time_slot.split(':')[1])
                start = datetime.combine(rec.booking_date, datetime.min.time()).replace(
                    hour=hour - 3, minute=minute, second=0)
                rec.start_time = start
                rec.end_time = start + timedelta(hours=2)
            else:
                rec.start_time = False
                rec.end_time = False

    @api.depends('start_time')
    def _compute_auto_cancel(self):
        for rec in self:
            if rec.start_time:
                rec.auto_cancel_time = rec.start_time + timedelta(minutes=10)
            else:
                rec.auto_cancel_time = False

    @api.constrains('group_size', 'booking_date', 'member_id', 'room_id', 'time_slot')
    def _check_booking(self):
        for rec in self:
            if rec.group_size < 3:
                raise ValidationError(
                    'Minimum group size is 3 people! / Minimum grup büyüklüğü 3 kişidir!')
            if rec.booking_date and rec.booking_date < fields.Date.today():
                raise ValidationError(
                    'Cannot book in the past! / Geçmiş tarih için rezervasyon yapılamaz!')
            if rec.booking_date and rec.member_id:
                daily_bookings = self.search_count([
                    ('member_id', '=', rec.member_id.id),
                    ('booking_date', '=', rec.booking_date),
                    ('state', 'not in', ['cancelled', 'rejected']),
                    ('id', '!=', rec.id),
                ])
                if daily_bookings >= 2:
                    raise ValidationError(
                        f'{rec.member_id.name} already has 2 bookings today! Max is 2 slots per day. / Günlük maksimum 2 rezervasyon!')
            if rec.time_slot and rec.room_id and rec.booking_date:
                overlap = self.search([
                    ('room_id', '=', rec.room_id.id),
                    ('booking_date', '=', rec.booking_date),
                    ('time_slot', '=', rec.time_slot),
                    ('state', 'in', ['pending', 'approved', 'active']),
                    ('id', '!=', rec.id),
                ])
                if overlap:
                    slot_label = dict(TIME_SLOTS).get(rec.time_slot, '')
                    raise ValidationError(
                        f"Room '{rec.room_id.name}' is already booked for {slot_label}! / Bu saat için oda dolu!")

    def _generate_qr(self):
        for rec in self:
            slot_label = dict(TIME_SLOTS).get(rec.time_slot, '')
            qr_data = (
                f"OSTIM LIBRARY BOOKING\n"
                f"ID: {rec.id}\n"
                f"Member: {rec.member_id.name}\n"
                f"Student ID: {rec.member_id.student_id or 'N/A'}\n"
                f"Room: {rec.room_id.name}\n"
                f"Date: {rec.booking_date}\n"
                f"Slot: {slot_label}\n"
                f"Group: {rec.group_size} people\n"
                f"REF: LIBRARY-{rec.id}-{rec.member_id.id}-{rec.room_id.id}"
            )
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            rec.qr_code = base64.b64encode(buffer.getvalue())
            rec.qr_code_text = qr_data

    def action_approve(self):
        self.state = 'approved'
        self._generate_qr()
        slot_label = dict(TIME_SLOTS).get(self.time_slot, '')
        self.message_post(body=f"Booking approved. Slot: {slot_label}. QR code generated.")

    def action_reject(self):
        self.state = 'rejected'
        self.message_post(body=f"Booking rejected. Reason: {self.rejection_reason or 'No reason given'}")

    def action_checkin(self):
        self.state = 'active'
        self.message_post(body="Member checked in.")

    def action_checkout(self):
        self.state = 'done'
        self.completed_at = fields.Datetime.now()
        self.message_post(body="Member checked out. Booking complete.")

    def action_cancel(self):
        self.state = 'cancelled'
        self.message_post(body="Booking cancelled.")

    def action_auto_cancel_check(self):
        now = fields.Datetime.now()
        bookings_to_cancel = self.search([
            ('state', '=', 'approved'),
            ('auto_cancel_time', '<=', now),
        ])
        for booking in bookings_to_cancel:
            booking.state = 'cancelled'
            booking.message_post(
                body="Auto cancelled — member did not check in within 10 minutes. / 10 dakika içinde giriş yapılmadığı için iptal edildi.")

    def action_cleanup_old_bookings(self):
        cutoff = fields.Datetime.now() - timedelta(hours=24)
        old_bookings = self.search([
            ('state', 'in', ['done', 'cancelled', 'rejected']),
            '|',
            ('completed_at', '<=', cutoff),
            ('write_date', '<=', cutoff),
        ])
        old_bookings.unlink()

    @api.model
    def _cron_auto_cancel(self):
        self.action_auto_cancel_check()

    @api.model
    def _cron_cleanup(self):
        self.action_cleanup_old_bookings()
