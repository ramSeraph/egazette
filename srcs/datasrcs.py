from . import central
from . import delhi
from . import bihar
from . import chattisgarh
from . import andhra
from . import karnataka

from . import maharashtra
from . import telangana
from . import tamilnadu

from . import odisha
from . import jharkhand
from . import madhyapradesh

from . import punjab
from . import uttarakhand
from . import haryana

from . import kerala
from . import himachal

from . import stgeorge

from . import goa
from . import csl 

from . import ladakh
from . import andaman
from . import nagaland
from . import lakshadweep
from . import dadranagarhaveli
from . import puducherry
from . import jammuandkashmir
from . import arunachal
from . import assam
from . import meghalaya
from . import mizoram
from . import sikkim
from . import tripura
from . import rajasthan
from . import gujarat
from . import uttarpradesh
from . import chandigarh
from . import manipur

from .datasrcs_info import srcinfos

srcdict = { \
'central_weekly'       : central.CentralWeekly, \
'central_extraordinary': central.CentralExtraordinary, \
'bihar'                : bihar.Bihar, \
'delhi_weekly'         : delhi.DelhiWeekly, \
'delhi_extraordinary'  : delhi.DelhiExtraordinary, \
'cgweekly'             : chattisgarh.ChattisgarhWeekly, \
'cgextraordinary'      : chattisgarh.ChattisgarhExtraordinary, \
'andhra_new'           : andhra.Andhra, \
'andhraarchive'        : andhra.AndhraArchive, \
'andhra_goir'          : andhra.AndhraGOIR, \
'karnataka'            : karnataka.Karnataka, \
'karnataka_erp'        : karnataka.KarnatakaErajyapatra, \
'maharashtra'          : maharashtra.Maharashtra, \
'telangana'            : telangana.Telangana, \
'telangana_goir'       : telangana.TelanganaGOIR, \
'tamilnadu'            : tamilnadu.TamilNadu, \
'odisha_egaz'          : odisha.OdishaEGazette, \
'odisha_govpress'      : odisha.OdishaGovPress, \
'jharkhand'            : jharkhand.Jharkhand, \
'madhyapradesh'        : madhyapradesh.MadhyaPradesh, \
'punjab'               : punjab.Punjab, \
'punjabdsa'            : punjab.PunjabDSA, \
'uttarakhand'          : uttarakhand.Uttarakhand, \
'himachal'             : himachal.Himachal, \
'himachalarchive'      : himachal.HimachalArchive, \
'haryana'              : haryana.Haryana, \
'haryanaarchive'       : haryana.HaryanaArchive, \
'kerala'               : kerala.Kerala, \
'keralacompose'        : kerala.KeralaCompose, \
'stgeorge'             : stgeorge.StGeorge, \
'keralalibrary'        : stgeorge.KeralaLibrary, \
'goa'                  : goa.Goa, \
'csl_weekly'           : csl.CSLWeekly, \
'csl_extraordinary'    : csl.CSLExtraordinary, \
'andaman'              : andaman.Andaman, \
'nagaland'             : nagaland.Nagaland, \
'lakshadweep'          : lakshadweep.Lakshadweep, \
'dadranagarhaveli'     : dadranagarhaveli.DadraNagarHaveli,\
'puducherry'           : puducherry.Puducherry, \
'ladakh'               : ladakh.Ladakh, \
'jammuandkashmir'      : jammuandkashmir.JammuAndKashmir, \
'arunachal'            : arunachal.Arunachal, \
'assam'                : assam.Assam, \
'meghalaya'            : meghalaya.Meghalaya, \
'mizoram'              : mizoram.Mizoram, \
'sikkim'               : sikkim.Sikkim, \
'tripura'              : tripura.Tripura, \
'rajasthan'            : rajasthan.Rajasthan, \
'gujarat'              : gujarat.Gujarat, \
'uttarpradesh'         : uttarpradesh.UttarPradesh, \
'chandigarh'           : chandigarh.Chandigarh, \
'manipur'              : manipur.Manipur, \
}

srchierarchy = {
    'central'    : ['central_weekly', 'central_extraordinary'],
    'csl'        : ['csl_weekly' , 'csl_extraordinary'],
    'delhi'      : ['delhi_weekly', 'delhi_extraordinary'],
    'chattisgarh': ['cgweekly', 'cgextraordinary'],
    'states'     : ['delhi', 'chattisgarh'] + 
                   list(set(srcdict.keys()) -
                        set(['central_weekly', 'central_extraordinary',
                             'csl_weekly', 'csl_extraordinary',
                             'delhi_weekly', 'delhi_extraordinary',
                             'cgweekly', 'cgextraordinary']))
}

def get_srcobjs(srclist, storage):
    srcobjs = []

    for src in srclist:
        srcinfo = srcinfos.get(src, {})
        if src in srchierarchy:
            srcobjs.extend(get_srcobjs(srchierarchy[src], storage))            
        if src in srcdict and srcinfo.get('enabled', True):
            obj = srcdict[src](src, storage)
            srcobjs.append(obj)

    return srcobjs
