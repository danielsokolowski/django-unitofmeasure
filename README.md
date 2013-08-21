====================
django-unitofmeasure
====================

Django Unit of Measurements type filed based on [pint](https://pint.readthedocs.org/en/latest/) - this is work in 
progress and absolutely is not complete. Current progress is shaped by existing project needs *however* this modules has 
been mothballed. A foray into multi-column database Django fields is a tricky affair; this code base in essence 
has a working solution but requires:

- `to_python` needs to be duplicated on the form level to properly display in ModelForms
- `virtual_fields` concepts as in GenericForeignKey should be utilized/reviewed
- native querying support should be provided
 
NOTE TO SELF: more then once you needed 'unit based field' in django and so do finish this on R&D time. 

Usage Example
-------------

Define your model and include an UOMField(...), which will create three fields on your model:

* name_of_uomfield_measured - a CharField based field named which stores the pre-normalized input value
* name_of_uomfield_unit - a CharField based field named which stores the normzlied unit of our our value
* name_of_uomfield - an extended Field which stores the actual value, on a database it is stored as a decimal.

		class Offer(models.Model):
			"""
			Main entity representing Offer/lead object
			"""
			### model options - "anything that's not a field"
			class Meta:
				ordering = ['created']
				...
			
			### Python class methods
			...
			
			### Django established method
			...
				
			### extra model functions
			...
			
			### custom managers
			objects = OfferManager()
			
			### model DB fields
			status = models.IntegerField(choices=OfferManager.STATUS_CHOICES, default=OfferManager.STATUS_ENABLED) #TODO: make this a bitfield !
			...
			amount_min = UOMField(normalized_units={'kg', 'liters'}, blank=True, null=True)
			...

This would result in the following model as represented by the model form in the Django admin:

<img style='margin-left: auto; margin-right: auto'
src="https://raw.github.com/danielsokolowski/django-unitofmeasure/master/django-unitofmeasure-model-form-fields.jpg"> 
