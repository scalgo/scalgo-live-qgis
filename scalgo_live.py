# -*- coding: utf-8 -*-
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtNetwork import QNetworkRequest, QNetworkReply
from qgis.core import QgsNetworkAccessManager, QgsMessageLog, QgsMapLayer, QgsProviderRegistry,QgsRasterLayer,QgsMapLayerRegistry,QgsCoordinateReferenceSystem 

import json

# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from scalgo_live_dialog import SCALGOLiveDialog
import os.path

from owslib.wmts import WebMapTileService

import urllib


from base import SCALGOWMTS

def log(msg):
    QgsMessageLog.logMessage(msg,"SCALGOLive")

class SCALGOLive:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        
        # Declare instance attributes
        self.actions = []
        self.menu = u'&Scalgo Live'
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'SCALGOLive')
        self.toolbar.setObjectName(u'SCALGOLive')

        self.settings = QSettings("SCALGO", "SCALGO Live Plugin")

        self.authCookies = None

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        # Create the dialog (after translation) and keep reference
        self.dlg = SCALGOLiveDialog()

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        self.dlg.loginButton.clicked.connect(self.loginButtonPressed)
        self.dlg.addButton.clicked.connect(self.addButtonPressed)
        self.dlg.quitButton.clicked.connect(self.quitButtonPressed)
        self.dlg.themesBox.currentIndexChanged.connect(self.themeChanged)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/SCALGOLive/icon.ico'
        self.add_action(
            icon_path,
            text=u'SCALGO Live',
            callback=self.run,
            parent=self.iface.mainWindow())


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                '&Scalgo Live',
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def login(self):
        def showError(err):
            self.dlg.loginErrorLabel.setText(err)
            self.dlg.loginErrorLabel.show()
            self.dlg.selectThemeLabel.hide()
            self.dlg.themesBox.hide()

        def showSuccess():
            self.dlg.loginErrorLabel.hide()
            self.dlg.selectThemeLabel.show()
            self.dlg.themesBox.show()

        self.authCookies = None
        password = None
        if (self.settings.contains("password")):
            password = self.settings.value("password")
        email = None
        if (self.settings.contains("email")):
            email = self.settings.value("email")

        if password == None or password == "" or email == None or email == "":
            showError("login failed, no email or password.")
            return False
        
        try:
            network = QgsNetworkAccessManager.instance()
            url = QUrl('https://scalgo.com/py/liveLogin/login')
            url.addQueryItem('usernameOrEmail', email)
            url.addQueryItem('password',password)
            
            req = QNetworkRequest(url)
            reply =network.get(req)
            while not reply.isFinished():
                QCoreApplication.processEvents()
            
            status_code=reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)

            if status_code == 200:
                showSuccess()        
                return True
            data = reply.readAll()
            
            if data is None:
                showError("Empty login response.")
                return False
                
            resp = json.loads(unicode(data,"utf-8"))
            if 'message' in resp:
                showError("Login failure: %s"%resp['message'])
            else:
                showError("Login failure: %s"%r.status_code)
        except TypeError as te:
            showError("Unknown login error: %s"%te)

        return False
        

    def setup(self):
        if not self.login():
            self.dlg.layersTab.setTabEnabled(0,False)
            return False

        if not self.getThemes():
            self.dlg.layersTab.setTabEnabled(0,False)
            return False

        self.dlg.layersTab.setTabEnabled(0,True)
    
        return True
        
    def getThemes(self):
        try:
            network = QgsNetworkAccessManager.instance()
            url = QUrl('https://scalgo.com/py/themelist')
            req = QNetworkRequest(url)
            reply =network.get(req)
            while not reply.isFinished():
                QCoreApplication.processEvents()

            status_code=reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) 
            data = reply.readAll()
            if data is None:
                QMessageBox.warning(self.dlg, "SCALGO Live Plugin",
                "Empty theme response.",
                QMessageBox.Close,
                QMessageBox.Close);
                return False
            content = json.loads(unicode(data,"utf-8"))
            
            themeList = content['themes'] 

            #populate theme combo box
            self.dlg.themesBox.currentIndexChanged.disconnect(self.themeChanged)            
            self.dlg.themesBox.clear()
        
            for t in themeList:
                name=t['name']
                identifier=t['identifier']
                self.dlg.themesBox.addItem(name,identifier)

            self.dlg.themesBox.currentIndexChanged.connect(self.themeChanged)

            #Take a stab at selecting a new theme
            requestedTheme = self.settings.value("theme") if self.settings.contains("theme") else None
        
            index = None #theme to use
            if requestedTheme is not None:
                #use requested theme                
                i = 0
                for t in themeList:
                    if t['identifier'] == requestedTheme:
                        index = i
                        break               
                    i+=1

            if index is None:
                #no theme found, trying heuristc
                ignoreThemes = {'global','scalgo'}
                preferThemes = {'livedenmarkfloodrisk'}
                index = 0 #use first theme if nothing else is found
                i = 0
                #find first theme that's preferred
                #if no such is found, find first that's not to be ignored
                for t in themeList:
                    i = i+1
                    identifier=t['identifier']
                    if identifier in ignoreThemes:
                        continue
                    elif identifier in preferThemes:
                        #found preferred theme, stop here
                        index= i-1
                        break
                    elif index == 0:
                        #not ignored, but not preferred either
                        #tentatively assign this theme but keep looking in
                        #case there is a preferred theme
                        index = i-1
                        continue

            
            self.dlg.themesBox.setCurrentIndex(-1)
            self.dlg.themesBox.setCurrentIndex(index)  

            return True
        except TypeError as te:
            QMessageBox.warning(self.dlg, "SCALGO Live Plugin",
                "Unknown theme error.",
                QMessageBox.Close,
                QMessageBox.Close);

      
    def themeChanged(self, index):
        if index < 0:
            return
        theme = self.dlg.themesBox.itemData(index)
        self.settings.setValue("theme",theme)
        self.refreshWMTS()
        self.refreshTreeView()


    def loginButtonPressed(self):
        password =  self.dlg.password.text()
        email =  self.dlg.email.text()
        self.settings.setValue("password",password)
        self.settings.setValue("email",email)   
        self.settings.remove("theme")

        self.dlg.themesBox.clear()
        self.setup()  
        
    def resetLayer(self):
        self.dlg.layer_title.setText("No Layer")
        self.dlg.layer_description.setText("Please select a layer.")
        self.resetTileType()

    def resetTileType(self):
        self.dlg.tiletype_group_box.setTitle("Layer type information.")
        self.dlg.tiletype_description.setText("Please select a layer to see information about the type.")
        self.resetThresholds()

    def resetThresholds(self):
        self.dlg.threshold1_value.hide()
        self.dlg.threshold1_title.hide()
        self.dlg.threshold1_unit.hide()     
        self.dlg.threshold1_description.hide()
    
    def handleTreeSelection(self,current):
        if len(current.indexes()) == 0:
            self.resetLayer()
            return

        lyr=current.indexes()[0].data(Qt.UserRole)
        if lyr is None:
            self.resetLayer()
            return
        
        self.dlg.layer_title.setText(lyr.simpleTitle)
        self.dlg.layer_description.setText(lyr.abstract)
        
        tt=self.wmts.tiletypes[lyr.contentType]
        self.dlg.tiletype_group_box.setTitle(tt.title)
        if tt.description is None or "TODO" in tt.description:
            self.dlg.tiletype_description.setText("No description")
        else:
            self.dlg.tiletype_description.setText(tt.description)
        self.dlg.tiletype_group_box.show()

        if len(tt.thresholds)>=1:
            #we only support the first threshold atm
            t = tt.thresholds[0]

            if t.description is None or "TODO" in t.description:
                self.dlg.threshold1_description.setText("No description")
            else:  
                self.dlg.threshold1_description.setText(t.description)

            self.dlg.threshold1_unit.setText("Unit: %s"%(tt.unit))
            self.dlg.threshold1_title.setText(t.title)
            self.dlg.threshold1_value.show()
            self.dlg.threshold1_title.show()
            self.dlg.threshold1_unit.show()            
            self.dlg.threshold1_description.show()
        else:
            self.resetThresholds()
      
    def refreshTreeView(self):
        view = self.dlg.layerTree
        view.setSelectionBehavior(QAbstractItemView.SelectRows)
        model = QStandardItemModel()
        view.setModel(model)
        #view.setUniformRowHeights(True)
        
        # populate data
        categories={}
        for tt in self.wmts.tiletypes.values():
            #merge tiletypeps with the same title 
            if tt.title not in categories:
                categories[tt.title] = { 'name': tt.title, 'layers': []}

        for lyr in self.wmts.scalgo_layers.values():
            def ignore(lyr):
                if ('rainevent' in lyr.contentType or 'rain_event' in lyr.contentType):
                    return True
                
                if ('_delin' in lyr.contentType):
                    return True
                return False

            if ignore(lyr):
                continue
            categories[self.wmts.tiletypes[lyr.contentType].title]['layers'].append(lyr)
            
        for category in categories.values():            
            children=[]

            for lyr in category['layers']:
                item = QStandardItem(lyr.simpleTitle)
                item.setEditable(False)
                item.setData(lyr, Qt.UserRole)
                item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)
                children.append(item)
            
            if children == []:
                continue
            
            parent = QStandardItem(category['name'])
            parent.setFlags(Qt.ItemIsEnabled)
            for child in children:
                parent.appendRow(child)
            model.appendRow(parent)

        self.dlg.layerTree.selectionModel().selectionChanged.connect(self.handleTreeSelection)
        
    def onTabChange(self, currentTab):
        pass

    def wmtsGetCapabilitiesUrl(self):
        theme = self.settings.value("theme")
        if self.settings.contains("password"):
            password = self.settings.value("password")
        else:
            log("Error getting getCapabilities URL: no password.")
            return None
        if self.settings.contains("email"):
            email = self.settings.value("email")
        else:
            log("Error getting getCapabilities URL: no email.")
            return None
        url = QUrl('https://scalgo.com/py/wmts/%s'%theme)
        url.addQueryItem('usernameOrEmail', email)
        url.addQueryItem('password',password)
        url.addQueryItem('REQUEST','GetCapabilities')
        return url

    def refreshWMTS(self):
        #LOAD FROM WEB
        url=self.wmtsGetCapabilitiesUrl()
        self.wmts = SCALGOWMTS(url=unicode(url.toEncoded(),"utf-8"))
    
    def addButtonPressed(self):
        a = self.dlg.layerTree.selectedIndexes()
        lyr = a[0].data(Qt.UserRole)
        
        if lyr is None:
            log("lyr is none")
            return

        #get threshold
        value=self.dlg.threshold1_value.value()

        args=lyr.wmtsArgs()


        email = None
        password = None

        if self.settings.contains("password"):
            password = self.settings.value("password")
        else:
            log("Error adding layer: no password.")
            return
        if self.settings.contains("email"):
            email = self.settings.value("email")
        else:
            log("Error adding layer: no email.")
            return
            
        args['login']=email
        args['request']='GetCapabilities'
        args['password']=password

        #parse the crs from urn:ogc:def:crs:EPSG::3857 to EPSG:3857
        qcrs = QgsCoordinateReferenceSystem()
        qcrs.createFromOgcWmsCrs(lyr.crs)
        crs=qcrs.authid()
        log("QGIS CRS is %s"%crs)

        url = self.wmtsGetCapabilitiesUrl()
        if url is None:
            log("AddButtonPressed: No url.")
            return

        #TODO, ideally extraTileArgs should be added here but backend cannot handle them whey they are encoded.
        #  url.addQueryItem("extraTileArgs","threshold=%s"%value)
        qgisArgs = {
        'contextualWMSLegend':0,
        'crs':crs,
        'dpimode':7,
        'format': args['format'],
        'layers': args['layer'],
        'styles': args['style'],
        'tileMatrixSet': args['tileMatrixSet'],
         'url': unicode(url.toEncoded(),"utf-8")+u'&extraTileArgs=threshold=%g'%value
        }
        log("QgsRasterLayer: %s"%qgisArgs)
        qgisURI=urllib.urlencode(qgisArgs)

        if (len(self.wmts.tiletypes[lyr.contentType].thresholds) > 0):
            tt=self.wmts.tiletypes[lyr.contentType]
            name =  "%s%s - %s"%(value,tt.unit,lyr.simpleTitle)
        else:
            name=lyr.simpleTitle

        qgis_wmts_lyr_manual = QgsRasterLayer(qgisURI, name, 'wms')
        if qgis_wmts_lyr_manual.isValid():
            QgsMapLayerRegistry.instance().addMapLayer(qgis_wmts_lyr_manual)
        else:
            log(qgis_wmts_lyr_manual.error().message())
            QMessageBox.warning(self.dlg, "SCALGO Live Plugin",
                "Error adding layer %s"%qgis_wmts_lyr_manual.error().message(),
                QMessageBox.Close,
                QMessageBox.Close);

    def quitButtonPressed(self):
        self.dlg.close()

    def run(self): 
        self.dlg.layersTab.currentChanged.connect(self.onTabChange)

        self.resetLayer()
    
        #initialize dialog with password and email values
        if self.settings.contains("password"):
            password = self.settings.value("password")
            self.dlg.password.setText(password)
        if self.settings.contains("email"):
            email = self.settings.value("email")
            self.dlg.email.setText(email)    
            
        self.setup()

        # show the dialog
        self.dlg.show()

        # Run the dialog event loop
        result = self.dlg.exec_()  