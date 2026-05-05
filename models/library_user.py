from odoo import models, fields, api
from odoo.exceptions import ValidationError

class LibraryUser(models.TransientModel):
    _name = 'library.user.wizard'
    _description = 'Create Library User'

    name = fields.Char(string='Full Name', required=True)
    email = fields.Char(string='Email', required=True)
    user_type = fields.Selection([
        ('portal', 'Student (Portal)'),
        ('staff', 'Staff'),
    ], string='User Type', required=True, default='portal')
    password = fields.Char(string='Password', required=True)

    def action_create_user(self):
        # Staff can only create portal users
        if self.env.user.has_group('library.group_library_staff') and \
           not self.env.user.has_group('library.group_library_admin') and \
           self.user_type == 'staff':
            raise ValidationError('Staff can only create Student (Portal) users!')

        # Create the Odoo user
        group_portal = self.env.ref('base.group_portal')
        group_internal = self.env.ref('base.group_user')

        new_user = self.env['res.users'].sudo().create({
            'name': self.name,
            'login': self.email,
            'password': self.password,
            'groups_id': [(6, 0, [group_portal.id if self.user_type == 'portal' else group_internal.id])],
        })

        # Assign library group
        if self.user_type == 'portal':
            library_group = self.env.ref('library.group_library_portal')
        else:
            library_group = self.env.ref('library.group_library_staff')

        library_group.sudo().write({'users': [(4, new_user.id)]})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'User Created',
                'message': f'{self.name} has been created successfully!',
                'type': 'success',
            }
        }
