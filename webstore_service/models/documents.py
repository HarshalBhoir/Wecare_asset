from openerp import models,fields,api,SUPERUSER_ID,tools,_
from datetime import datetime,date
from openerp.exceptions import UserError, AccessError

class file_document(models.Model):
	_name = 'file.document'
	
	name = fields.Char(string="File Name")
	type = fields.Selection([('url','URL'),('file','File')])
	url = fields.Char(string="URL")
	file = fields.Binary(string="File Content")
	file_name = fields.Char(string="File Name")
	