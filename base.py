from builtins import super

from qgis.core import QgsMessageLog, QgsMapLayer, QgsProviderRegistry
from owslib.wmts import WebMapTileService

from xml.etree import ElementTree
import re

def remove_namespaces_qname(doc):
    for el in doc.getiterator():
        # clean tag
        q = ElementTree.QName(el.tag)
        if q is not None:
            el.tag = q.local
            # clean attributes
            for a, v in el.items():
                q = ElementTree.QName(a)
                if q is not None:
                    if namespaces is not None:
                        del el.attrib[a]
                        el.attrib[q.local] = v
    return doc

#from owslib
_OWS_NS = '{http://www.opengis.net/ows/1.1}'
_WMTS_NS = '{http://www.opengis.net/wmts/1.0}'
_XLINK_NS = '{http://www.w3.org/1999/xlink}'
_SCALGO_NS = '{http://www.scalgo.com/wmts-ext/1.0}'

_SCALGO_IDENTIFIER= _SCALGO_NS+"Identifier"
_SCALGO_TITLE= _SCALGO_NS+"Title"


class Threshold(object):
    def __init__(self,wmts,xml):
        self.wmts = wmts
        self.xml = xml;
        
    @property
    def description(self):
        node = self.xml.find(_SCALGO_NS + "Description")
        if node is not None :
            return node.text
        return None

    @property
    def title(self):
        return self.xml.find(_SCALGO_TITLE).text
    
    @property 
    def default(self):
        return self.xml.find(_SCALGO_NS + "Default").text    

class DynamicType(object):
    def __init__(self, wmts,xml):
        super(DynamicType,self).__init__()
        self.xml = xml      
        self.wmts = wmts  
        self.thresholds = []
        foundThresholds=self.xml.findall(_SCALGO_NS+"Threshold")
        for txml in foundThresholds:
            threshold=Threshold(self.wmts,txml)
            self.thresholds.append(threshold)
    

    @property
    def identifier(self):
        return self.xml.find(_SCALGO_IDENTIFIER).text

    @property
    def title(self):
        return self.xml.find(_SCALGO_TITLE).text

    @property 
    def unit(self):
        return self.xml.find(_SCALGO_NS + "Unit").text

    @property
    def description(self):
        return self.xml.find(_SCALGO_NS + "Description").text


class SCALGOWMTS(WebMapTileService):
    
    def __init__(self,**kwargs):
        #login=kwargs.pop('login')
        #password=kwargs.pop('password')        
        super(SCALGOWMTS,self).__init__(**kwargs)
        
        #Build Dynamic Types
        foundTiletypes=self._capabilities.findall(_WMTS_NS+"Contents/"+_SCALGO_NS+"DynamicType")

        self.tiletypes={}
        for tiletype in foundTiletypes:          
            dt=DynamicType(self,tiletype)            
            self.tiletypes[dt.identifier]=dt

        self.scalgo_layers={}
        for (a,b) in self.contents.iteritems():
            a=b.id
            layer=SCALGOLayer(self,b.id)
            self.scalgo_layers[layer.id] = layer
    
    def getTileURL(self):
        # GetTile URL
        url = self.getOperationByName('GetTile').methods
        return url[0].get("url")        

class SCALGOLayer(object):
    def __init__(self, wmts, idx):
        super(SCALGOLayer,self).__init__()
        self.wmts = wmts
        self.id = idx        

    @property
    def layerWMTS(self):
        return self.wmts[self.id]

    @property
    def contentType(self):
        LAYER_TAG=_WMTS_NS+"Layer"
        c=self.wmts._capabilities.find(_WMTS_NS+"Contents")
        lyr=c.find(LAYER_TAG+"/["+_OWS_NS+"Identifier='%s']"%self.id)
        link=lyr.find("%sDynamicTypeLink/%sDynamicType"%(_SCALGO_NS,_SCALGO_NS))
        return  link.text

    @property
    def simpleTitle(self):
        LAYER_TAG=_WMTS_NS+"Layer"
        c=self.wmts._capabilities.find(_WMTS_NS+"Contents")
        lyr=c.find(LAYER_TAG+"/["+_OWS_NS+"Identifier='%s']"%self.id)
        simpleTitle=lyr.find(_SCALGO_NS+"SimpleTitle")
        return simpleTitle.text

    @property
    def title(self):
        return self.wmts.contents[self.id].title

    @property
    def abstract(self):        
        LAYER_TAG=_WMTS_NS+"Layer"
        c=self.wmts._capabilities.find(_WMTS_NS+"Contents")
        lyr=c.find(LAYER_TAG+"/["+_OWS_NS+"Identifier='%s']"%self.id)
        #abstract=lyr.findall(_OWS_NS+"Abstract[lang('en')]")
        abstract=lyr.findall(_OWS_NS+"Abstract")[0]
        s=ElementTree.tostring(abstract,method="xml")
        s=re.sub("<[a-zA-Z0-9]*:","<",s)
        s=re.sub("</.*:","</",s)
        s=re.sub("<Abstract.*>","",s)
        s=re.sub("</Abstract>","",s)
        return s

    @property
    def crs(self):
        # Tile Matrix Set & SRS, pick the first one
        tile_matrix_set = self.wmts.tilematrixsets[self.layerWMTS.tilematrixsetlinks.keys()[0]]
        return tile_matrix_set.crs

    def wmtsArgs(self):
        response={}

        response['layer'] = self.id
        qgis_wms_formats=["image/png","image/jpg"]
        
        # Tile Matrix Set & SRS, pick the first one
        tile_matrix_set = self.wmts.tilematrixsets[self.layerWMTS.tilematrixsetlinks.keys()[0]]
        response['tileMatrixSet'] = tile_matrix_set.identifier
                
        # Format definition
        response['format']= "image/png"

        # Style definition
        response['style'] = self.layerWMTS.styles.keys()[0]
        
        return response    

def log(msg):
    QgsMessageLog.logMessage(msg,"SCALGOLive")
