#-*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup

from utils import utils
from db.mongo_db import SilpyMongoClient

#In this file we process data comming from
#http://www.diputados.gov.py

class DiputadosScrapper(object):
    
    #en el sitio de diputados se hace un
    #request por cada tab del detalle del diputado:
    # Datos Currículum Comisiones Proyectos» Contactos 
    
    def get_member_list(self):
        url = 'http://www.diputados.gov.py/ww2/?pagina=dip-listado'
        response = requests.get(url)
        soup = BeautifulSoup(response.text)
        table = soup.find('table', {'class':'tex'})
        tr_list = table.find_all('tr', recursive=False)
        tr_list.pop(0)#discard first row, header
        members = []
        for tr in tr_list:
            member = {}
            td_list = tr.find_all('td', recursive=False)
            id = td_list[0].img['src']
            member['diputado_id'] = id[id.rindex('/')+2:id.rindex('.')]
            img = td_list[0].img['src']
            member['img_src'] = 'http://www.diputados.gov.py/'+ img[img.index('/')] #so we can download image afterwards
            member['name'] = td_list[1].text.strip()
            member['link'] = td_list[1].a['href']
            members.append(member)
        return members
    
    def get_member_details(self, member_id):
        url = 'http://www.diputados.gov.py/ww2/index.php?pagina=cv&id='+ member_id
        response = requests.get(url)
        soup = BeautifulSoup(response.text)
        tables = soup.find_all('table',{'class':'tex'})#the child table is the one we need
        tbody = tables[1].table
        member = {}
        td_list = tbody.find_all('td')
        member['departament'] = td_list[1].text.strip()
        member['city'] = td_list[3].text.strip()
        member['party'] = td_list[5].text.strip()
        member['bench'] = td_list[7].text.strip()
        member['profession'] = td_list[9].text.strip()
        member['office'] = td_list[11].text.strip()
        member['phone'] = td_list[13].text.strip()
        member['web_site'] = td_list[15].text.strip()
        member['email'] = td_list[17].text.strip()                
        return member
        
    def get_member_cv(self, member_id):
        url = 'http://www.diputados.gov.py/ww2/index.php?pagina=cv-curriculum&id=' + member_id 
        response = requests.get(url)
        soup = BeautifulSoup(response.text)
        tables = soup.find_all('table', {'class':'tex'})#the child table is the one we need
        #return as plain text
        return tables[1].getText()

    #deprecated: extracted from silpy
    # def get_member_committees(self, member_id):
    #     
    #     url = 'http://www.diputados.gov.py/ww2/index.php?pagina=cv-comisiones&id='+member_id
    #     response = requests.get(url)
    #     soup = BeautifulSoup(response.text)        
    #     table = soup.find('table', {'class':'tex'})
    #     tables = soup.find_all('table', {'class':'tex'})#the child table is the one we need
    #     tbody = tables[1].tbody

    def get_articles(self):
        day = '21'
        month = '05'
        year = '2015'
        requests.post('http://www.diputados.gov.py/ww2/index.php?pagina=noticias-lista',
                      files={'dia': (None, day), 'mes': (None, month), 
                             'anho': (None, year), 'sb': (None, '1'), 
                             'btnBuscar': (None, 'Buscar')})

    def get_members_data(self):
        mongo_client = SilpyMongoClient()
        ds = DiputadosScrapper()
        members = ds.get_member_list()
        for m in members:
            print "Procesando diputado " + m['name']
            id = m['diputado_id']
            m.update(ds.get_member_details(id))
            cv = ds.get_member_cv(id)
            m['cv'] = cv
            mongo_client.update_diputado_by_name(m)
    
#print ds.get_member_details(dict(diputado_id='271'))