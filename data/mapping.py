"""
/***************************************************************************
Name                 : Database Model/Widget Mapping Classes
Description          : Classes that enable the mapping of database model 
                       attributes to the corresponding UI widgets for rapid
                       building of custom STDM forms.
Date                 : 28/January/2014 
copyright            : (C) 2014 by John Gitau
email                : gkahiu@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import *
from PyQt4.QtGui import QApplication, QMessageBox, QDialog

from qgis.gui import *
from qgis.core import *

from stdm.ui.helpers import valueHandler, ControlDirtyTrackerCollection
from stdm.ui.notification import NotificationBar,ERROR,WARNING, SUCCESS

from stdm.data.configuration import entity_model

__all__ = ["SAVE","UPDATE","MapperMixin","QgsFeatureMappperMixin"]

'''
Save mode enum for specifying whether a widget is in 'Save' mode - when creating 
a new record or 'Update' mode, which is used when updating an existing record.
'''
SAVE = 2200
UPDATE = 2201

class _AttributeMapper(object):
    '''
    Manages a single instance of the mapping between a database model's attribute
    and the corresponding UI widget.
    '''
    def __init__(self, attributeName, qtControl, model, pseudoname="", isMandatory = False, \
                 customValueHandler = None,bindControlOnly = False):
        '''
        :param attributeName: Property name of the database model that is to be mapped.
        :param qtControl: Qt input widget that should be mapped to the model's attribute.
        :param model: STDM model to which the attribute name belongs to.
        :param isMandatory: Flag to indicate whether a value is required from the input control.
        :param customValueHandler: Instance of a custom value handler can be provided if it does not exist amongst 
        those in the registered list.
        :param bindControlOnly: The model will not be updated using the control's value. This is used to only 
        update the control value using the model value when the mapper is in 'Update' mode.
        '''
        self._attrName = attributeName
        self._control = qtControl
        self._model = model
        self._isMandatory = isMandatory
        self._bindControlOnly = bindControlOnly
        
        if customValueHandler == None:
            self._valueHandler = valueHandler(qtControl)()
        else:
            self._valueHandler = customValueHandler()
            
        if not self._valueHandler is None:
            self._valueHandler.setControl(qtControl)
            
        self._pseudoname = attributeName if pseudoname == "" else pseudoname
            
    def attributeName(self):
        '''
        Attribute name.
        '''
        return self._attrName
    
    def pseudoName(self):
        '''
        Returns the pseudoname of the mapper. This is useful when the attribute name refers to a foreign key
        and as such cannot be used for displaying user-friendly text; then in such a case, the pseudoname can
        be used for displaying a user friendly name.
        '''
        return self._pseudoname
    
    def control(self):
        '''
        Referenced Qt input widget.
        '''
        return self._control

    def set_model(self, model):
        """
        Sets model to the attributeMapper.
        :param model: The model to be set
        :type model: SQLAlchemy Model object
        """
        self._model = model

    def model(self):
        """
        Returns the model.
        :return: The model object.
        :rtype: SQLAlchemy Model object
        """
        return self._model

    def valueHandler(self):
        '''
        Return value handler associated with this control.
        '''
        return self._valueHandler
    
    def controlValue(self):
        '''
        Returns the value in the control.
        '''
        return self._valueHandler.value()
    
    def isMandatory(self):
        '''
        Returns whether the field is mandatory.
        '''
        return self._isMandatory

    def setMandatory(self,mandatory):
        '''
        Set field should be mandatory
        '''
        self._isMandatory = mandatory
        
    def bindControl(self):
        '''
        Sets the value of the control using the model's attribute value.
        '''
        if hasattr(self.model(), self._attrName):
            attrValue = getattr(self.model(), self._attrName)
            self._valueHandler.setValue(attrValue)
            
    def bindModel(self):
        '''
        Set the model attribute value to the control's value.
        The handler is responsible for adapting Qt and Python types as expected
        and defined by the model.
        '''
        if hasattr(self.model(), self._attrName):
            controlValue = self._valueHandler.value()
            # The to conditions below fix the issue of
            # saving data for QGIS forms and other forms.
            # QGIS only recognizes QDate so we have to
            # keep the control value as QData and
            # convert it to python date before
            # saving it to the database here.
            if isinstance(controlValue, QDate):
                controlValue = controlValue.toPyDate()

            if isinstance(controlValue, QDateTime):
                controlValue = controlValue.toPyDateTime()

            setattr(self.model(), self._attrName, controlValue)


class MapperMixin(object):
    '''
    Mixin class for use in a dialog or widget, and manages attribute mapping.
    '''
    def __init__(self, model, entity):
        '''
        :param model: Callable (new instances) or instance (existing instance
        for updating) of STDM model.
        '''
        if callable(model):
            self._model = model()
            self._mode = SAVE
        else:
            self._model = model
            self._mode = UPDATE
        self.entity = entity
        self._attrMappers = []
        self._attr_mapper_collection={}
        self._dirtyTracker = ControlDirtyTrackerCollection()
        self._notifBar = None
        self.is_valid = False
        self.saved_model = None
        # Get document objects
        self.entity_model = entity_model(entity)
        self.entity_model_obj = self.entity_model()
        #Initialize notification bar
        if hasattr(self,"vlNotification"):
            self._notifBar = NotificationBar(self.vlNotification)
        
        #Flag to indicate whether to close the widget or dialog once model has been submitted
        #self.closeOnSubmit = True
        
    def addMapping(self,attributeName,control,isMandatory=False,
                   pseudoname='', valueHandler=None, preloadfunc=None):
        '''
        Specify the mapping configuration.
        '''
        attrMapper = _AttributeMapper(attributeName,control,self._model,pseudoname,isMandatory,valueHandler)
        self.addMapper(attrMapper,preloadfunc)
        
    def addMapper(self,attributeMapper,preloadfunc = None):
        '''
        Add an attributeMapper object to the collection.
        Preloadfunc specifies a function that can be used to prepopulate the control's value only when
        the control is on SAVE mode.
        '''
        if self._mode == SAVE and preloadfunc != None:
            attributeMapper.valueHandler().setValue(preloadfunc)
        
        if self._mode == UPDATE:
            #Set control value based on the model attribute value
            attributeMapper.bindControl()
            
        #Add control to dirty tracker collection after control value has been set
        self._dirtyTracker.addControl(attributeMapper.control(), attributeMapper.valueHandler())
            
        self._attrMappers.append(attributeMapper)
        self._attr_mapper_collection[attributeMapper.attributeName()] = attributeMapper

    def saveMode(self):
        '''
        Return the mode that the mapper is currently configured in.
        '''
        return self._mode

    def attribute_mapper(self, attribute_name):
        """
        Returns attribute mapper object corresponding to the the given
        attribute.
        :param attribute_name: Name of the attribute
        :type attribute_name: str
        :return: Attribute mapper
        :rtype: _AttributeMapper
        """
        return self._attr_mapper_collection.get(attribute_name, None)

    def setSaveMode(self,mode):
        '''
        Set the mapper's save mode.
        '''
        self._mode = mode
        
    def setModel(self, stdmModel):
        '''
        Set the model to be used by the mapper.
        '''
        self._model = stdmModel
        
    def model(self):
        '''
        Returns the model configured for the mapper.
        '''
        return self._model
        
    def setNotificationLayout(self,layout):
        '''
        Set the vertical layout instance that will be used to display
        notification messages.
        '''
        self._notifBar = NotificationBar(layout)
        
    def insertNotification(self,message,mtype):
        '''
        There has to be a vertical layout, named 'vlNotification', that
        enables for notifications to be inserted.
        '''
        if self._notifBar:
            self._notifBar.insertNotification(message, mtype)   
            
    def clearNotifications(self):         
        '''
        Clears all messages in the notification bar.
        '''
        if self._notifBar:
            self._notifBar.clear()
            
    def checkDirty(self):
        '''
        Asserts whether the dialog contains dirty controls.
        '''
        isDirty = False
        msgResponse = None
        
        if self._dirtyTracker.isDirty():
            isDirty = True
            msg = QApplication.translate(
                "MappedDialog",
                "Would you like to save changes before closing?"
            )
            msgResponse = QMessageBox.information(
                self, QApplication.translate(
                    "MappedDialog","Save Changes"
                ),
                msg,
                QMessageBox.Yes|QMessageBox.No|QMessageBox.Cancel
            )
            
        return isDirty,msgResponse
    
    def closeEvent(self,event):
        '''
        Raised when a request to close the window is received.
        Check the dirty state of input controls and prompt user to
        save if dirty.
        ''' 
        isDirty,userResponse = self.checkDirty()
        
        if isDirty:
            if userResponse == QMessageBox.Yes:
                # We need to ignore the event so that validation and
                # saving operations can be executed
                event.ignore()
                self.submit()
            elif userResponse == QMessageBox.No:
                event.accept()
            elif userResponse == QMessageBox.Cancel:
                event.ignore()
        else:
            event.accept()
    
    def cancel(self):
        '''
        Slot for closing the dialog.
        Checks the dirty state first before closing.
        '''
        isDirty,userResponse = self.checkDirty()
        
        if isDirty:
            if userResponse == QMessageBox.Yes:
                self.submit()
            elif userResponse == QMessageBox.No:
                self.reject()
            elif userResponse == QMessageBox.Cancel:
                pass
        else:
            self.reject()
    
    def preSaveUpdate(self):
        '''
        Mixin classes can override this method to specify any operations that
        need to be executed prior to saving or updating the model's values.
        It should return True prior to saving.
        '''
        return True
    
    def postSaveUpdate(self, dbmodel):
        '''
        Executed once a record has been saved or updated. 
        '''
        self.saved_model = dbmodel

    def validate_all(self):
        """
        Validate the entire form.
        :return:
        :rtype:
        """
        errors = []
        for attrMapper in self._attrMappers:
            error = self.validate(attrMapper)

            if error is not None:
                self._notifBar.insertWarningNotification(error)
                errors.append(error)
        return errors

    def validate(self, attrMapper, update=False):
        """
        Validate attribute.
        :param attrMapper: The attribute
        :type attrMapper: _AttributeMapper
        :param update: Whether the validation is on update or new entry
        :type update: Boolean
        :return: List of error messages or None
        :rtype: list or NoneType
        """
        error = None

        field = attrMapper.pseudoName()
        column_name = attrMapper.attributeName()
        if column_name in self.entity.columns.keys():
            column = self.entity.columns[column_name]
        else:
            return

        if column.unique:
            column_obj = getattr(self.entity_model, column_name, None)
            if not update:
                result = self.entity_model_obj.queryObject().filter(
                    column_obj == attrMapper.valueHandler().value()).first()
            else:
                id_obj = getattr(self.entity_model, 'id', None)
                result = self.entity_model_obj.queryObject().filter(
                    column_obj == attrMapper.valueHandler().value()).filter(
                    id_obj != self.model().id).first()

            if result is not None:
                msg = QApplication.translate("MappedDialog",
                                             "field value should be unique.")
                error = '{} {}'.format(field, msg)

        if column.mandatory:
            if attrMapper.valueHandler().value() == \
                    attrMapper.valueHandler().default():
                # Notify user
                msg = QApplication.translate("MappedDialog",
                                             "is a required field.")
                error = '{} {}'.format(field, msg)

        return error
    
    def submit(self, collect_model=False, save_and_new=False):
        """
        Slot for saving or updating the model.
        This will close the dialog on successful submission.
        :param collect_model: If set to True only returns
        the model without saving it to the database.
        :type collect_model: Boolean
        :param save_and_new: A Boolean indicating it is
        triggered by save and new button.
        :type save_and_new: Boolean
        """
        if not self.preSaveUpdate():
            return
        
        self.clearNotifications()
        self.is_valid = True

        # Validate mandatory fields have been entered by the user.
        errors = []
        for attrMapper in self._attrMappers:

            if self._mode == 'SAVE':
                error = self.validate(attrMapper)
            else: # update mode
                error = self.validate(attrMapper, True)
            if error is not None:
                self._notifBar.insertWarningNotification(error)
                errors.append(error)

        if len(errors) > 0:
            self.is_valid = False

        if not self.is_valid:
            return

        # Bind model once all attributes are valid
        for attrMapper in self._attrMappers:
            attrMapper.set_model(self.model())
            attrMapper.bindModel()

        if not collect_model:
            self._persistModel(save_and_new)

    def _persistModel(self, save_and_new):
        """
        Saves the model to the database and shows a success message.
        :param save_and_new: A Boolean indicating it is triggered by save and
        new button.
        :type save_and_new: Boolean
        """
        try:
            # Persist the model to its corresponding store.
            if self._mode == SAVE:
                self._model.save()
                if not save_and_new:
                    QMessageBox.information(
                        self, QApplication.translate(
                            "MappedDialog","Record Saved"
                        ),
                        QApplication.translate(
                            "MappedDialog",
                            "New record has been successfully saved."
                        )
                    )

            else:
                self._model.update()
                QMessageBox.information(
                    self,
                    QApplication.translate("MappedDialog","Record Updated"),
                    QApplication.translate(
                        "MappedDialog",
                        "Record has been successfully updated.")
                )

        except Exception as ex:
            QMessageBox.critical(
                self,
                QApplication.translate(
                    "MappedDialog", "Data Operation Error"
                ),
                QApplication.translate(
                    "MappedDialog",
                    u'The data could not be saved due to '
                    u'the error: \n{}'.format(ex.args[0])
                )
            )
            self.is_valid = False

        # Close the dialog
        if isinstance(self, QDialog) and self.is_valid:
            self.postSaveUpdate(self._model)
            if not save_and_new:
                self.accept()

    def clear(self):
        """
        Clears the form values.
        """
        for attrMapper in self._attrMappers:
            attrMapper.valueHandler().clear()

