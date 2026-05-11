from odoo import models, fields, api
from odoo.exceptions import ValidationError

class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Library Book'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Title', required=True, tracking=True)
    author = fields.Char(string='Author', required=True)
    isbn = fields.Char(string='ISBN')
    edition = fields.Char(string='Edition')
    volume = fields.Char(string='Volume')
    book_type = fields.Selection([
        ('physical', 'Physical Book'),
        ('ebook', 'E-Book'),
    ], string='Book Type', required=True, default='physical')
    download_url = fields.Char(string='Download URL')
    price = fields.Float(string='Sale Price')
    for_sale = fields.Boolean(string='Available for Sale', default=False)
    total_copies = fields.Integer(string='Total Copies', default=1)
    available_copies = fields.Integer(string='Available Copies', compute='_compute_available_copies', store=True)
    state = fields.Selection([
        ('available', 'Available'),
        ('borrowed', 'Borrowed'),
        ('sold_out', 'Sold Out'),
    ], string='Status', compute='_compute_state', store=True)
    borrow_ids = fields.One2many('library.borrow', 'book_id', string='Borrow History')
    borrow_count = fields.Integer(string='Times Borrowed', compute='_compute_borrow_count')
    category = fields.Char(string='Category')
    language = fields.Char(string='Language', default='English')
    publish_year = fields.Integer(string='Publish Year')
    active = fields.Boolean(string='Active', default=True)
    cover_image = fields.Binary(string='Cover Image', attachment=True)
    reservation_ids = fields.One2many('library.reservation', 'book_id', string='Reservations')
    cover_image_filename = fields.Char(string='Cover Filename')

    @api.depends('borrow_ids', 'borrow_ids.state', 'total_copies')
    def _compute_available_copies(self):
        for book in self:
            borrowed = len(book.borrow_ids.filtered(lambda b: b.state == 'borrowed'))
            book.available_copies = book.total_copies - borrowed

    @api.depends('available_copies', 'total_copies')
    def _compute_state(self):
        for book in self:
            if book.book_type == 'ebook':
                book.state = 'available'
            elif book.available_copies <= 0:
                book.state = 'borrowed'
            else:
                book.state = 'available'

    @api.depends('borrow_ids')
    def _compute_borrow_count(self):
        for book in self:
            book.borrow_count = len(book.borrow_ids)

    @api.constrains('download_url', 'book_type')
    def _check_ebook_url(self):
        for book in self:
            if book.book_type == 'ebook' and not book.download_url:
                raise ValidationError('E-Books must have a download URL!')

    def get_book_display_domain(self):
        display = self.env['ir.config_parameter'].sudo().get_param('library.book_display', 'all')
        if display == 'physical':
            return [('book_type', '=', 'physical')]
        elif display == 'ebook':
            return [('book_type', '=', 'ebook')]
        return []
