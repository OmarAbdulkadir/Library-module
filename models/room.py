from odoo import models, fields, api

class LibraryRoom(models.Model):
    _name = 'library.room'
    _description = 'Library Room'

    name = fields.Char(string='Room Name', required=True)
    capacity = fields.Integer(string='Capacity', default=10)
    has_computers = fields.Boolean(string='Has Computers', default=False)
    computer_count = fields.Integer(string='Number of Computers', default=0)
    computers_available = fields.Integer(
        string='Computers Available',
        compute='_compute_computers_available',
        store=True
    )
    description = fields.Text(string='Description')
    state = fields.Selection([
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Under Maintenance'),
    ], string='Status', default='available')

    booking_ids = fields.One2many('library.room.booking', 'room_id', string='Bookings')

    current_occupancy = fields.Integer(
        string='Current Occupancy',
        compute='_compute_current_occupancy',
        store=True
    )
    occupancy_percent = fields.Float(
        string='Occupancy %',
        compute='_compute_current_occupancy',
        store=True
    )
    is_crowded = fields.Boolean(string='Is Crowded', compute='_compute_crowded', store=True)

    @api.depends('booking_ids', 'booking_ids.state')
    def _compute_current_occupancy(self):
        for room in self:
            active_bookings = room.booking_ids.filtered(lambda b: b.state == 'active')
            room.current_occupancy = len(active_bookings)
            if room.capacity > 0:
                room.occupancy_percent = (room.current_occupancy / room.capacity) * 100
            else:
                room.occupancy_percent = 0

    @api.depends('current_occupancy', 'capacity')
    def _compute_crowded(self):
        for room in self:
            if room.capacity > 0:
                room.is_crowded = (room.current_occupancy / room.capacity) >= 0.8
            else:
                room.is_crowded = False

    @api.depends('booking_ids', 'booking_ids.state', 'computer_count')
    def _compute_computers_available(self):
        for room in self:
            if room.has_computers:
                active_bookings = len(room.booking_ids.filtered(
                    lambda b: b.state == 'active' and b.needs_computer
                ))
                room.computers_available = room.computer_count - active_bookings
            else:
                room.computers_available = 0

    def action_set_maintenance(self):
        self.state = 'maintenance'

    def action_set_available(self):
        self.state = 'available'
