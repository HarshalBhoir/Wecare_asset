from openerp import models,fields,api,SUPERUSER_ID,tools,_
from datetime import datetime,date
from openerp.exceptions import UserError, AccessError

class auto_responce(models.Model):
	_name = 'auto.responce'
	
	name = fields.Char(string="Code")
	box = fields.Boolean(string="Box")
	description = fields.Html(string="Description")
	diff_desc = fields.Html(string="Description after box")
	account = fields.Html(string="Account")
	
	