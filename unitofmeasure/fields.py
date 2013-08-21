from django.db.models.fields import Field, CharField
from django.db.models import SubfieldBase
from django import forms
from decimal import Decimal
from pint import UnitRegistry
from collections import Iterable
from django.core.exceptions import ValidationError

import logging
import inspect
logger = logging.getLogger(__name__)

forms.CharField

class UOMField(Field): #rename this to UOMModelField to be explicit as ModelField != FormField obvious but forgotten
	"""
	Three column based field that allows for storing and manipulation of physical measurements. 
	
	UOMFields is an extended Field() objects and hence takes the same arguements plus one more 'normalized_unit';
	this is what entered values will be converted to, if conversion is not possible an error is thrown which
	propergates to the Forms as needed. When accessing UOMField on models an instance of 'pint.quantity.Quantity' is
	returned. 
	
	For one UOMField defined on a model three supporting fields will be created:
	
	* <name_of_uomfield>_measured - a CharField based field named which stores the pre-normalized input value
	* <name_of_uomfield>_unit - a CharField based field named which stores the normzlied unit of our our value
	* <name_of_uomfield> - an extended Field which stores the actual value, on a database it is stored as a decimal.
	
	At the moment fields should be treated as seperate when performing queories:
	
	> Model.objects.filter(amount_unit = 'kg', amount = 1000)
	  
	"""
	description = "Two column based field that allows for storing and manipulation of physical measurements. See " \
				  "class.__doc__ for more"
	#__metaclass__ = SubfieldBase # this ensure to_python() will be called every time an instance of the 
								 # field is assigned a value. see link below: 
								 # https://docs.djangoproject.com/en/dev/howto/custom-model-fields/#modelforms-and-custom-fields
								 # however this doesn't allow us to call our to_python with aditional arguments
								 # so we explictly overide the __set__ and __get__ ourselfs 
								 # IMPORTANT: do note that we must also then provide to_python on form level
								 # see: https://docs.djangoproject.com/en/1.3/howto/custom-model-fields/#modelforms-and-custom-fields
								 # see: http://stackoverflow.com/questions/8895688/raising-validationerror-in-a-custom-fields-to-python-method-breaks-admin-form
								 
	unitregistry = UnitRegistry() # shared unitregistry for all UOMFields #TODO: move this onto module level?
	# this should be an instance variable normalized_units = [] 

	
	def __init__(self, normalized_units, *args, **kwargs):
		assert isinstance(normalized_units, Iterable) and isinstance(normalized_units, str) == False, "Argument "\
							"'normalized_unit' must type 'Iterable' but not 'str' yet got '{0}".format(type(normalized_units))
		for unit in normalized_units:
			assert isinstance(unit, str), "Unit {0} in normalized_units list must be type 'str' but got {1}" \
							.format(type(unit))
			assert hasattr(self.unitregistry, unit), "Unit specified {0} for 'normalized_unit' option not found " \
													"in UnitRegistry.".format(normalized_unit)
		
		#TODO: maybe add a check that it makes no sense to have normalized_units of same physical reference i.e. KG, G 
		# 	   because of our coercing loop in to_python
		
		self.normalized_units = normalized_units # instance variable
		kwargs['help_text'] = "{0}Normalized to '{1}' unit(s).".format(
										kwargs['help_text'] + '. ' if 'help_text' in kwargs else '',
										' or '.join(normalized_units))

		super(UOMField, self).__init__(*args, **kwargs)  #will for example populate self.name

	
	def __get__(self, model_instance, type=None):
		if model_instance is None:
			raise AttributeError('Can only be accessed via an a model instance.')
		return model_instance.__dict__[self.name]

	def __set__(self, model_instance, value):
		model_instance.__dict__[self.name] = self.to_python(value, model_instance) #TODO: should we do self.model_instance
																				   #BUT on the self instance level not class
																				   # 

	def contribute_to_class(self, cls, name):
		# let's sneak in our supporting foo_measured and foo_normalized_unit field and add it to our model definition
		foo_measured = CharField(help_text="Stores pre-normalized value of the '{0}' UOMField field. Modify " \
											 "directly at your own risk as there is no sync checking logic " \
											 "at present.".format(name),
										max_length=255, blank=True)
		foo_measured.creation_counter = self.creation_counter # we must ensure our supporting fields are init first  
		cls.add_to_class("{0}_measured".format(name), foo_measured) # when this increments self.creation_counter by 1
		del foo_measured  # the price to pay for no scope brackets and hence anonymous methods

		foo_unit = CharField(help_text="The unit of the normalized value in '{0}' UOMField field. Modify" \
										 " at your own risk as there is no sync checking logic at present" \
										 .format(name),
										max_length=255, blank=True,
										choices=[(x, x) for x in self.normalized_units])
		foo_unit.creation_counter = self.creation_counter # we must ensure our supporting fields are init first
		cls.add_to_class("{0}_unit".format(name), foo_unit)
		del foo_unit  # the price to pay for no scope brackets and hence anonymous methods

		# do default - we must ensure that our supporting fields are added first to the model so they 
		# avaiable when accessing our main (this) field and that's why do the code above and overide the creation_cunter
		super(UOMField, self).contribute_to_class(cls, name) 
		
		# Now we need to hook ourself as the attribute of the model itself 
		# in Django this is called attaching the 'descriptor protocol'  
		setattr(cls, self.name, self)		

	def get_internal_type(self):
		return "DecimalField" # best representation on the database layer plus our magnitude is always Decimal objects
							  # note without the max_digits, decimal places, etc limitations, this is flexible.
#
	def to_python(self, value, model_instance=None): # django's Field.clean() bulitin calls self.to_python(value)
												 # so we must provide a default or overide clean(), specifing 
													 # model_instance=None seems ok as during debuging value is already
													 # in our Quantity(...) object, so we should never need model_insttance
		"""	We must always return our custom Object or None - do the most minimum validation here as it 
		there isn't always a pretty form to catch the ValidationError - do full validation in fields validation"""
		if value == None:
			return None
		
		# convert to Quantity - we pass the value as is to Quantity and let it do the conversion any errors we catch
		try:
			q = self.unitregistry.Quantity(value)
		except Exception as e:
			raise ValidationError("Field '{0}' can not parse '{1}' of type '{2}' into a valid quantity. Underlying " \
								  " pint module parsing exception is: '{3}'".format(self.attname, value, type(value), e))
		
		return q
		# now we have Quantity object however it might be dimensionless which is fine as long as 'foo_unit' is defined
		if q.dimensionless:
			assert model_instance != None, "Should not be possible, do we need to code custom .clean()?"
			if getattr(model_instance, "{0}_unit".format(self.attname)) == "":
				raise ValidationError("For field '{0}' dimensionless '{1}' quantities are not allowed, please specify"
									  " the unit on the model's '{0}_unit' field or provide the unit with your" 
									  " input, ex. '{2} kg' ".format(self.attname, q, value))
			else:
				# note we can just Dimensionless Quantity * Unit or we get a Dimensionless quantity that is not 
				#  - see https://github.com/hgrecco/pint/issues/52
				try:
					q = self.unitregistry.Quantity(q.magnitude, 
												   getattr(model_instance, "{0}_unit".format(self.attname))) 
				except Exception as e: 
					raise ValidationError("Field '{0}' could not convert dimensionless '{1}' into a unit '{2}' " \
										  "(set in '{0}_unit'). Underling pint module exception was: '{3}'" \
										  .format(self.attname,
												  q, 
												  getattr(model_instance, "{0}_unit".format(self.attname)), 
												  e))
				
		# now using a dirty hack ensure magnitude is Decimal from default float (ex 1.1 + 2.2 conundrum)
		q._magnitude = Decimal(str(q.magnitude))
		
		# convert to our normalized units
		normalized = False  # if stays False then we failed to convert and should throw an error 
		for unit in self.normalized_units:
			try:
				q.ito(unit)
				normalized = True
				break
			except:
				pass 
		if normalized == False:
			raise ValidationError("Field '{0}' can not normalize value '{1}' of quantity '{2}' into allowed '{3}' choices."\
								.format( self.attname, value, q,' or '.join(self.normalized_units)))
		
		# update supporting fields 
		# TODO: this don't seem to fit here best, perhaps move it onto clean method and 
		# an dacutally call model_instance.FIELD.clean() again since we are updating it?
		# BUT no need to do clean it is done already!
		if model_instance: #TODO again do we just define a self.model_instance
			setattr(model_instance, "{0}_unit".format(self.attname), unit)
			#setattr(model_instance, "{0}_measured".format(self.attname), value) #FIXME: this need to go on save_form field?
			
		return q

	def formfield(self, form_class=None, **kwargs):
		#from pydevsrc import pydevd;pydevd.settrace('192.168.2.8', stdoutToServer=True, stderrToServer=True, suspend=True)  # @UnresolvedImport
		#formfield = super(UOMField, self).formfield(form_class, **kwargs)
		# patch the formfield
		#formfield.to_python = self.to_python
		# Clone and put on Python path: https://github.com/tenXer/PyDevSrc, place this in your settings_development.py, and place your 'break' points in Eclipse
		#from pydevsrc import pydevd;pydevd.settrace('192.168.2.8', stdoutToServer=True, stderrToServer=True, suspend=True)  # @UnresolvedImport
		kwargs['model_instance'] = self.model_instance
		return super(UOMField, self).formfield(UOMFormField, **kwargs)

	#def validate(self, value, model_instance):
	#	""" Validate our value, keep in mind that to_python is called first then validate is called on output from 
	#	to_python"""
	#	super(UOMField, self).validate(value, model_instance) # things like blanks, nulls, choices checks
		

	def get_prep_value(self, value):
		if value == None:
			return Value
		if value == "":
			return value
		return value.magnitude


class UOMFormField(forms.CharField):
	def __init__(self, max_length=None, min_length=None, *args, model_instance, **kwargs):
		self.model_instance = model_instance
		super(UOMFormField, self).__init__(max_length, min_length, *args, **kwargs)
	def to_python(self, value):
		pythonized_value = 

#class UOMFieldCreator(object):
#	"""
#	A class that provides a way to set the attribute on the model, using what django calls the 'Descriptor' protocol.
#	
#	For example the to_python stack is 'to_python <  __set__' - the crucial thing here is we can access the model
#	instance and pass it our to_python method - this is the proper way of doing it rather then 
#	inspect.currentframe().f_back.f_locals['model_instance'] hacks
#	
#	see: django/db/models/fields/sublcassing.py
#	"""
#	def __init__(self, field):
#		self.field = field
#
#	def __get__(self, obj, type=None):
#		
#		if obj is None:
#			raise AttributeError('Can only be accessed via an instance.')
#		return obj.__dict__[self.field.name]
#
#	def __set__(self, obj, value):
#		
#		obj.__dict__[self.field.name] = self.field.to_python(value)