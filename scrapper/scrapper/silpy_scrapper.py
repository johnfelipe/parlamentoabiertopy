#-*- coding: utf-8 -*-
'''
Created on Feb 26, 2015

@author: demian
'''

import traceback
import httplib
import json
import urllib
import hashlib 
import requests
import unicodedata
import datetime
import time

from bs4 import BeautifulSoup, CData
from HTMLParser import HTMLParser

from utils import utils


silpy_host = "sil2py.senado.gov.py"
NO_ROWS_FOUND= 'Sin registros...'

class SilpyHTMLParser(object):

    def extraer_items_menu(self, html):
        #retorna un diccionario con los
        #items del menu principal
        soup = BeautifulSoup(html)
        main_menu_form = soup.find(id='formPreference')
        menu_items = main_menu_form.find_all('li')
        menu = {}
        for i in menu_items:
            anchor = i.a
            if anchor != None:
                menu[i.text] = i.a['onclick']
        return menu
          
    def parse_parlamentary_data(self, html):
        #TODO:extract designaciones 
        #http://silpy.congreso.gov.py/formulario/VerDetalleTramitacion.pmf?q=VerDetalleTramitacionVerDetalleTramitacion%2F101470
        partial_soup = BeautifulSoup(html)
        soup = BeautifulSoup(html)
        tbody = soup.find(id="formMain:dataTable_data")
        tr_list = tbody.find_all("tr")
        rows = []
        str_images = '/images'
        for tr in tr_list:
            #this is a table, of course it has a fixed length
            #0 = row_id, incremental
            #1 = img (we extract the MP id from the image name
            #2 = name
            #3 = committees: div with list of divs
            #4 = projects: link using the extracted id from (2)
            row = {}
            td_list = tr.find_all("td")
            row['index'] = td_list[0].text.strip()
            name = td_list[2].text.strip()
            row['name'] = name[:name.index('-')].strip()
            row['party'] = name[name.index('-')+1:].strip()
            row['projects_body_param'] = td_list[4].text.strip() #parameter to invoke projects 
            row_index = int(row['index'])-1
            #extraction of MP id
            src = td_list[1].div.img['src']
            if str_images in src:
                #TODO: download img!
                #http://sil2py.senado.gov.py/images/100081.jpg
                row['img'] = 'http://'+ silpy_host + src
                row['id'] = src[len(str_images)+1: len(src)].replace('.jpg','')
                #extraction of formMain
                #formMain goes in the following request to get
                # committee details  list_projects_by_committee(body_param)
                #lis = td_list[3].div.div.find_all("li")
                #work_div contains two subdivs, one for projects and the other 
                #for designations
                return rows
                work_divs = td_list[3].div.find_all('div', recursive=False)
                committees_lis = work_divs[0].find_all("li")
                committees = []
                for li in committees_lis:
                    js_call = li.a['onclick']
                    committee = {'text': li.text.strip(), 'js_call': js_call}
                    committees.append(committee)
                row['committees'] = committees
                #designation extraction
                #apparently not all rows have a designations div
                if len(work_divs) > 1:
                    designation_lis = work_divs[1].find_all("li")
                    designations = []
                    for li in designation_lis:                         
                        js_call = li.a['onclick']
                        designation = {'text': li.text.strip(), 'js_call': js_call}
                        designations.append(designation)
                    row['designations'] = designations
            rows.append(row)            
        return rows

    def parse_projects_by_parlamentary(self, html):
        soup = BeautifulSoup(html)
        #this tbody contains the actual data from the html comming from
        #http://sil2py.senado.gov.py/formulario/verProyectosParlamentario.pmf?q=verProyectosParlamentario%2F100081
        #the id increments for each section
        #TODO: count sections?
        projects = []
        #ids are generated dynamically
        #so we search for the div with attr=role and value=tablist
        #and extract its id
        content_id = soup.find(id='formMain').find_all('div', {'role': 'tablist'})[0]['id']
        tabs_div = soup.find(id=content_id)
        h3_list = tabs_div.find_all('h3', recursive=False)#number of tabs                         
       
        for i in range(0,len(h3_list)):
            id=content_id + ":%i:dataTable_data" %(i)
            tbody=soup.find(id=id)
            projects += self.parsear_lista_de_proyectos(tbody)
        return projects

    #quiza ni necesitamos ya que podemos quitar las estadisticas localmente
    def _extract_statistics_table(self, html):
        #extracts data from the statistics table in resources/projects_by_committee.html
        soup = BeautifulSoup(html)
        committee_table = soup.find(id="formMain:panelComision")
        committee = committee_table.tr.td.text
        status = committee[committee.index('[')+1 : committee.index(']')]
        statistics_div = soup.find(id="formMain:j_idt85")
        #th_list = statistics_div.table.thead.find_all("th")
        statistics = []
        if statistics_div:
            tr_list = statistics_div.table.tbody.find_all("tr")
            statistics = []
            for tr in tr_list:
                td_list = tr.find_all("td")
                values = {}
                values["quantity"] = td_list[0].text
                values["stage"] = td_list[1].text 
                statistics.append(values)
        else:
            write_html(html)  
        return statistics

    def _extract_projects_by_committee(self, html):
        #extracts data from the results table in resources/projects_by_committee.html
        soup = BeautifulSoup(html)
        result_tbody = soup.find(id = "formMain:dataTable_data")
        tr_list = result_tbody.find_all("tr")
        #TODO: set this as header
        description = soup.find(id="formMain:denominacion")       
        return self.parsear_lista_de_proyectos(result_tbody)

    def parsear_lista_de_proyectos(self, result_tbody, id=None):
        #result_body is the tbody which contains the rows from the table
        #Ex.: result_tbody = soup.find(id = "formMain:dataTableProyecto_data") 
        #if the id is not None then we extract the result_tbody with that id        
        if id is not None:
            result_tbody = result_tbody.find(id)
        
        tr_list = result_tbody.find_all("tr", recursive=False)
        projects = []
        
        for tr in tr_list:
            td_list = tr.find_all("td", recursive=False)            
            if td_list != None and len(td_list) > 0:
                project = {}
                td0 = td_list[0]

                if td0.div != None:
                    project['title'] = td0.a.text                   
                span_list = td0.find_all('span')
                if span_list != None and len(span_list) > 0:
                    project['type'] = span_list[0].text.strip()
                    texts_rows = span_list[1].text.split('\n')
                    #el id del proyecto se quita del icono "Votar Por Proyecto"
                    #siendo el id la ultima parte numerica del link.
                    #Ej: http://sil2py.senado.gov.py/votacion/VotarProyecto.pmf?q=votarProyecto%2F1112
                    #id=1112
                    # El link al detalle de tramitacion seria:
                    #silpy.congreso.gov.py/formulario/VerDetalleTramitacion.pmf?q=VerDetalleTramitacion%2F1112
                    subtables = span_list[1].find_all('table')
                    last_table = subtables[len(subtables) - 1] #la tabla con la imagen del tipito con el altoparlante
                    id = last_table.tbody.td.a['href'][::-1]
                    id = id[:id.index('%') - 2][::-1]
                    project['id'] = id
                    
                    if len(texts_rows) > 1:#sometimes there are just counted comments                     
                        entry_date, date = texts_rows[1].split(":")
                        folder, id = texts_rows[3].split(":")
                        project['entry_date'] = date.strip()
                        project['file'] = id.strip()                        
                        #eliminar o aumentar esta seccion
                        #hay mas elementos pero por ahi no son importantes
                        if len(texts_rows) >= 3: #there is also a mensaje section, and other
                            subtable = span_list[1].table #texts_rows, len(texts_rows)
                            trs = subtable.find_all("tr")
                            for tr in trs:
                                tr_spans = tr.find_all('span')
                                if len(tr_spans) > 0:
                                    messages = []
                                    for span in tr_spans:
                                        messages.append(span.text.replace("|", "").strip())
                                    project['messages'] = messages

                #segunda columna: Etapa
                if len(td_list) >= 1:
                    td1 = td_list[1]
                    td1_span_list = td1.find_all('span')
                    #print "td1_span_list " + str(td1_span_list)
                    if len(td1_span_list) > 1:
                        project['stage'] = {'chamber': td1_span_list[0].text, 
                                             td1_span_list[1].text : td1_span_list[2].text}
                if len(project) != 0:        
                    projects.append(project)
        return projects

    def parse_bills_list_by_date(self, html):
        soup = BeautifulSoup(html)
        tbody = soup.find(id='formMain:dataTable_data')
        tr_list = tbody.find_all('tr', recursive=False)
        bills = []
        #id = last_table.tbody.td.a['href'][::-1]
        #id = id[:id.index('%') - 2][::-1]
        #project['id'] = id
        for tr in tr_list:
            td_list= tr.find_all('td', recursive=False)
            texts = td_list[2].text.split('\n')
            js_call = td_list[2].a['onclick']
            
            info = {}
            info['type'] = texts[0].strip()
            info['heading'] = ''.join(texts[1:]).strip()
            bill = {}                               
            bill['nro_ley'] = td_list[1].text
            bill['info'] = info
            bill['camara'] = td_list[3].text
            bill['js_call'] = js_call
            bills.append(bill)
        return bills

    def parsear_lista_de_proyectos_dialog(html):
        #recibe el hmtl de la lista de sesiones
        #con el dialog de la lista de proyectos
        soup = BeautifulSoup(html)
        tbody = soup.find(id = 'formMain:dataTableProyecto_data')
        tr_list = tbody.find_all('tr')
        proyectos = self.parsear_lista_de_proyectos(tbody)
    
    def parsear_lista_sessiones(self, html):
        #recibe el html despues de buscar las sesiones por periodo 
        proyectos = []
        soup = BeautifulSoup(html)
        periodo = soup.find(id = 'formMain:idPeriodoParlamentario_label')
        periodo = periodo.text.strip()
        tbody = soup.find(id = 'formMain:dataTable_data')
        tr_list = tbody.find_all('tr')
        for tr in tr_list:
            td_list = tr.find_all('td')
            if len(td_list) > 0:
                proyecto = {}
                proyecto['index'] = td_list[0].text.strip()
                proyecto['fecha'] = td_list[1].div.text.strip()
                proyecto['nro_sesion'] = td_list[2].text.strip()
                proyecto['tipo_sesion'] = td_list[3].text.strip()
                proyecto['anexos_js_call'] = td_list[4].button['onclick']
                proyecto['verProyectos_js_call'] = td_list[5].button['onclick']
                proyectos.append(proyecto)
        return proyectos

    def extract_session_attachment(self, html):
        #anexos de la sesion
        soup = BeautifulSoup(html)
        anexos_table = soup.find(id="formMain:dataTableDetalle").table
        tr_list = anexos_table.tbody.find_all('tr')
        anexos = []
        for tr in tr_list:
            td_list = tr.find_all('td')
            #td_list[0].text.strip() 
            nombre = td_list[1].text.strip()
            #discard size and replace spaces with underscore
            nombre = nombre[:nombre.find("\n")].replace(" ", "_")
            anexo = {'name': nombre,
                     'registered_date': td_list[2].text.strip(),
                     'button_id': td_list[3].button['id']}
            anexos.append(anexo)
        return anexos

    def extraer_comisiones_por_periodo(self, html):
        soup = BeautifulSoup(html)
        tbody = soup.find(id='formMain:dataTable_data')
        tr_list = tbody.find_all('tr', recursive=False)
        comisiones = []

        for tr in tr_list:
            comision = {}
            td_list = tr.find_all('td', recursive=False)
            comision['name'] = td_list[1].text.strip()
            comision['type']  = td_list[2].text.strip()
            comision['chamber'] = td_list[3].text.strip()
            comision['member_js_call'] = td_list[4].div.button['onclick']
            comisiones.append(comision)
        return comisiones

    def extract_project_details(self, html):
        bill = {}
        #this changes over time
        section_id_number = utils.var_form_id
        #extract the numeric part of the id, it changes over time
        nid=html[html.find('expedienteCamara') - 12 :html.find('expedienteCamara')][9:]
        nid = nid.replace(':', '')
        base_id = 'j_idt'+nid #this part use used as base of the id
        soup = BeautifulSoup(html)
        #formMain:j_idt81_content
        #j_idt80:j_idt81_content
        #j_idt66:j_idt67_content
        content_id = base_id+':j_idt'+ str(int(nid) + 1) +'_content'
        info_div = soup.find(id=base_id+':j_idt'+ str(int(nid) + 1) +'_content')
        spans = info_div.find_all('span')
        info = {}
        info['file'] = info_div.find(id=base_id+':expedienteCamara').text.strip()
        info['type'] = info_div.find(id=base_id + ':idTipoProyecto').text.strip()
        info['importance'] = info_div.find(id=base_id + ':idUrgencia').text.strip()
        info['entry_date'] = info_div.find(id=base_id + ':fechaIngreso').text.strip()
        info['iniciativa'] = info_div.find(id=base_id + ':idTipoIniciativa').text.strip()
        info['origin'] = info_div.find(id=base_id + ':idOrigen').text.strip()
        info['message'] =info_div.find(id=base_id + ':numeroMensaje').text.strip()
        info['heading'] =info_div.find(id=base_id + ':acapite').text.strip()
        
        if info_div.find(id=base_id + ':idMateria'):
            info['subject'] = info_div.find(id=base_id + ':idMateria').text.strip()
        
        bill['info'] = info
        #Etapa de la Tramitación
        #id='j_idt80:j_idt81_content'
        etapa = {}
        main_table = info_div
        etapas_table = main_table.table.table
        status_statges_list = etapas_table.find_all('span', {'class': "itemResaltado3D-2"})
        stage_substage = status_statges_list[1].text.split("/")
        etapa['stage'] = stage_substage[::-1][1]#next to last element
        etapa['sub_stage'] = stage_substage[::-1][0]#last element 
        etapa['status'] = status_statges_list[0].text.strip()
        bill['stage'] = etapa

        #need to show sections and download related files
        menu = self._extract_project_sections_menu(soup, section_id_number)
        bill['sections_menu'] = menu
        #documentos de iniciativa            
        bill['documents'] = self._extract_project_documents(soup, section_id_number)
        #detalle de tramitacion
        if 'paperworks' in menu:
            bill['paperworks'] = self._extract_project_paperworks(soup, section_id_number)
        #autores
        bill['authors'] = self._extract_project_authors(soup, menu['authors']['id'])
        # ?? dictamenes formMain:j_idt124:j_idt203
        if 'directives' in menu:
            bill['directives'] = self._extract_project_directives(soup, menu['directives']['id'])
        #resoluciones y mensajes -> ?
        if 'resolutions_and_messages' in menu:
            bill['resolutions_and_messages'] = \
                self._extract_projects_resolutions_and_messages(soup, menu['resolutions_and_messages']['id'])
        if 'laws_and_decrees' in menu:
            bill['laws_and_decrees'] = self._extract_laws_and_decrees(soup, menu['laws_and_decrees']['id'])
        return bill

    def _extract_project_sections_menu(self, soup, idnumber):        
        #parse lateral menu and extract sections 
        #sections must be show to click on buttons
        #clicking is done by the navigator
        sections_menu = {}
        sections_ul = soup.find(id='formMain:j_idt'+idnumber).ul
        a_list = sections_ul.find_all('a')
        for a in a_list:            
            #the text of the section is followd by [N]
            #where N is the number of rows in that section
            sections_menu['text'] = a.text.strip()
            text = a.text
            key = None
            if u'Tramitación' in text: 
                key = 'paperworks'
            elif u'Documentos de Iniciativa' in text:
                key = 'documents'
            elif u'Autores'in text:
                key = 'authors'
            elif u'Dictámenes'in text:
                key = 'directives'
            elif u'Resoluciones y Mensajes'in text:
                key = 'resolutions_and_messages'
            elif u'Leyes y Decretos'in text:
                key = 'laws_and_decrees' #?
            else:
                key = text.strip()
            sections_menu[key] = {'text' : a.text.strip(),
                                  'href': a['href'],
                                  'id': a['href'].replace('#','')}
        return sections_menu

    def _extract_file_static_link(self, a_element):
        #extracts the file static link from the mailto icon
        link = a_element['href']
        link = link[link.index('http'):]
        link = link.replace('%3A',':').replace('%3F','?')
        return link

    def _extract_project_authors(self, soup, id):
        autores_tbody = soup.find(id=id).tbody
        autores_tr_list = autores_tbody.find_all('tr')
        autores = []
        for tr in autores_tr_list:
            if tr.td.img:
                reverse = tr.td.img['src'][::-1]
                id = reverse[reverse.index('.')+1: reverse.index('/')][::-1]
                autores.append({'id': id, 'name': tr.text.strip()})
            else:
                autores.append({'id': 0, 'name':  tr.td.text.strip()})
        return autores

    def _extract_laws_and_decrees(self, soup, id):
        main_tbody = soup.find(id= id).table.tbody#'formMain:j_idt124:j_idt281_data')
        result = []
        tr_list = main_tbody.find_all('tr', recursive=False)
        for tr in tr_list:
            inner_tr_list = tr.tbody.find_all('tr', recursive=False)
            info = {}
            for itr in inner_tr_list:
                if len(itr.text.strip()) > 1:
                    info['texts'] = itr.text.strip().split('\n')
            button = tr.find('button')
            info['button_id'] = button['id']
            info['link'] = self._extract_file_static_link(tr.find('a'))
            name = button.parent.text
            name = name[name.index(button.text):]
            info['name'] = name.replace(button.text,'').strip()
            result.append(info)
        return result

    def _extract_projects_resolutions_and_messages(self, soup, id):
        resolutions_and_messages = []
        main_tbody = soup.find(id= id).table.tbody#''formMain:j_idt124:j_idt220_data')
        if main_tbody:
            tr_list = main_tbody.find_all('tr', recursive=False)
            for tr in tr_list:
                res = {}
                td_list = tr.find_all('td', recursive=False)
                #1. CAMARA DE SENADORES
                #Resolución :
                #Mensaje : 334 15/04/2014
                #Versions: only buttons apparently, easy
                buttons = []
                links = []
                dt_list = td_list[1].find_all('dt')
                index = 0
                for dt in dt_list:
                    buttons.append({'index': index,
                                    'name': dt.text.replace('ui-button ', '').strip(),
                                    'id': dt.button['id']})

                    links.append(self._extract_file_static_link(dt.a))
                    index += 1
                res['buttons'] = buttons
                res['links'] = links
                
                #the first column contains a table within a table
                #iterate over rows and extracts elements
                #columns resolution/message label - id(number) - date(may or may not be present)
                inner_tr_list = td_list[0].table.tbody.find_all('tr', recursive=False)
                #1st row - chamber
                res['index'] = inner_tr_list[0].text.strip().split('.')[0]
                res['chamber'] = inner_tr_list[0].text.strip().split('.')[1]
                #2nd row is a table resolution: id - date
                final_tr_list = inner_tr_list[1].table.tbody.find_all('tr', recursive=False)
                #it has 2 rows and up to 3 columns
                #extracts empty elements from list
                resolution = [x for x in final_tr_list[0].text.split('\n') if x != '']
                message = [x for x in final_tr_list[1].text.split('\n') if x != '']
                res['resolution_number'] = resolution[0].split(':')[1].strip()
                if len(resolution) > 1:
                    res['resolution_date'] = resolution[1].strip()
                if len(message) > 1:
                    res['message_date'] = message[1].strip()
                res['message_number'] = message[0].split(':')[1].strip()
                res['result'] = inner_tr_list[3].text.strip()
                resolutions_and_messages.append(res)
        return resolutions_and_messages
     
    def _extract_project_documents(self, soup, section_id_number):
        docs_tbody = soup.find(id='formMain:j_idt' + section_id_number + ':dataTableDetalle_data')
        if docs_tbody == None:
            return None
        documents = []
        index = 0
        tr_list = docs_tbody.find_all('tr', recursive=False)
        for tr in tr_list:
            if tr.text.strip() == 'Sin registros...':
                #nothing found
                break
            td_list = tr.find_all('td',recursive=False)
            doc = {}
            doc['type'] = td_list[0].text.strip()
            name = td_list[2].text.strip().split('\n')
            doc['name'] = name[0].strip()
            doc['file_size'] = name[1].strip().replace('[', '').replace(']', '')
            doc['registration_date'] = td_list[2].text.strip()
            doc['button_id'] = tr.button['id']#will be pressed somewhere
            doc['index'] = index #list index correlates with table row index which is part of the button_id
            #todo: link
            doc['link'] = self._extract_file_static_link(td_list[2].a)
            index += 1
            documents.append(doc)
        return documents
        
    def _extract_project_directives(self, soup, id):
        #TODO: result column presents different structures
        #first row is committee:
        #   1. Economía, Cooperativismo, Desarrollo e Integración Económica Latinoamericana
        #   chamber
        main = soup.find(id=id)#''formMain:j_idt124:j_idt203')
        if main == None:
            return None
        directives_tbody = main.find('tbody')
        tr_list = directives_tbody.find_all('tr', recursive=False)
        directives = []
        index = 0
        for tr in tr_list:
            directive = {}
            td_list = tr.find_all('td', recursive=False)
            text = td_list[1].find('li').text
            res_date =  text[:text.find('\n')].split(' ')
            directive['result'] = res_date[0]
            directive['date'] = res_date[1]
            directive['index'] = index
            #will be pressed somewhere
            buttons = []
            buttons_elements = td_list[1].find_all('button')
            #mailto links
            a_elements = td_list[1].find_all('a')
            directive['links'] = []
            b_index = 0
            for b in buttons_elements:
                #extract here index of the button
                #that will be used in the body of the request
                buttons.append({'index': b_index,
                                'id': td_list[1].button['id']})                
                directive['links'].append(self._extract_file_static_link(a_elements[b_index]))
                b_index +=1
                
            directive['buttons'] = buttons
            #download links
            directives.append(directive)
            index += 1
        return directives
            
    def _extract_project_paperworks(self, soup, nid):
        #recieves a soup object from method extract_project_details
        paperworks = []
        tbody_content = soup.find(id='formMain:j_idt'+ str(nid) +':dataTableTramitacion_data')#'formMain:j_idt124:dataTableTramitacion_data')
        paperwork_tr_list = tbody_content.find_all('tr', recursive=False)
        for tr in paperwork_tr_list:
            paperwork = {}
            td_list = tr.find_all('td', recursive=False)
            paperwork['index'] = td_list[0].text.strip()
            paperwork['session'] = td_list[1].text.strip()
            paperwork['date'] = td_list[2].text.strip()
            #TODO: extraccion de etapa se puede generalizar
            if len(td_list) >= 1:
                td1 = td_list[3]
                td1_span_list = td1.find_all('span')
                #print "td1_span_list " + str(td1_span_list)
                if len(td1_span_list) > 1:
                    paperwork['chamber'] = td1_span_list[0].text                    
                    paperwork['stage'] = td1_span_list[1].text.strip() + " " \
                    + td1_span_list[2].text.strip()
            #resultado: the last column
            results_li= td_list[4].find_all('li',recursive=False)
            result_text = td_list[4].text#find(text=True, recursive=False)
            result = {}
            text = td_list[4].find(text=True)
            #Next element(s), those could be one of the following
            #1 - it might be a list (<ul><li></li></ul>)
            #2 - might be an <a> in which case it is followed by a text
            #3 - A text (the actual result), followed by <br>(two), and a text
            # with the next step
            ul = td_list[4].find_all('ul')
            a = td_list[4].find_all('a')
            br = td_list[4].find_all('br')
            if a:
                #in this case the result is on the hr
                #preceeded by the word sentido
                div_text = td_list[4].text
                result['details'] = text.split(',')
                div_text = div_text[len(text):]
                result['value'] = div_text[len('Sentido'):].strip()
            elif br:
                #in this case the text is where the bills goes to afterwards
                #and the title is the actual result
                result['value'] = text
                result['next_step'] = br[0].text.strip()
            elif ul:
                result['value'] = text
                result['details'] = []
                li_list = ul[0].find_all('li')
                for li in li_list:
                    result['details'].append(li.text.strip())
            #todo clean up result before adding
            paperwork['result'] = result
            paperworks.append(paperwork)
        return paperworks
       
    def extraer_miembros_por_comision(self, html):
        soup = BeautifulSoup(html)
        miembros_div = soup.find('div', {'class' : 'ui-datatable-scrollable-body'})
        tr_list =  miembros_div.table.find_all('tr')
        p = None
        for tr in tr_list:
            p = {}
            td_list = tr.find_all('td', recursive=False)
            reverse = td_list[0].img['src'][::-1]
            p['id'] = reverse[reverse.index('.'): reverse.index('/')][::-1]
            p['name'] = td_list[1].text.strip()
            p['chamber'] = td_list[2].text.strip()
            p['post'] = td_list[3].text.strip()
        return p

    def procesar_proyectos_por_comite(self, data):
        soup = BeautifulSoup(data)
        stats = self._extract_statistics_table(html=data)
        projects = self._extract_projects_by_committee(html=data)
        return stats, projects

    def number_of_rows_found(self, html):
        #numero de registros encontrados en la tabla
        #aparentemente se utiliza la misma clase css en diferentes tablas
        # TODO: "Sin registros..." found return None
        soup = BeautifulSoup(html)
        #check if there's something found
        tbody = soup.find('tbody', id='formMain:dataTable_data')
        if tbody.text == NO_ROWS_FOUND:
            return None
        
        th = soup.find('th', {'class':"ui-datatable-header ui-widget-header"})
        text = th.table.tbody.tr.td.text
        number_of_rows = text[0 : text.index('registros recuperados')]
        return int(number_of_rows.strip())
    
    def extract_viewstate(self, html):
        soup = BeautifulSoup(html)
        #print soup
        viewState_container = soup.find(id="javax.faces.ViewState")
        viewState = None
        if viewState_container.name == 'input': 
            viewState = viewState_container['value']
        elif viewState_container.name == 'update':
            viewstate = viewState_container.text     
        return viewState


from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as E
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from utils.utils import FileDownloadError, var_form_id

class SilpyNavigator(object):
    """
    Naviagation Flow for http://silpy.congreso.gov.py
    """

    def __init__(self, browser=None, navigate=True):
        self.parser = SilpyHTMLParser()
        self.mongo_client = SilpyMongoClient()#TODO: use only one instance
        if not navigate:
            print 'WARNING: not using webdriver, for development purposses only'
            return
        if browser:
            self.browser=browser
        else:
            self.browser = utils.get_new_browser()
            self.browser.get("http://" + silpy_host + "/main.pmf")                               

    def close_driver(self):
       self.browser.close() 

    #deprecated
    def make_webdriver_wait(self, by, waited_element, browser=None):
        try:
            if browser == None:
                browser = self.browser
            wait = WebDriverWait(browser, 15)
            wait.until(EC.presence_of_element_located((by, waited_element)))
            print "Page is ready! Loaded: " + waited_element
        
        except TimeoutException:
            print "Loading took too much time! for element: " + waited_element
                   
    def count_table_rows(self):
        #wait for css_element
        #TODO: css element as parameter
        css_element = ".ui-widget-content.ui-datatable-even"
        utils.make_webdriver_wait(By.CSS_SELECTOR, css_element, self.browser)
        return self.parser.number_of_rows_found(self.browser.page_source)
        
    def _call_menu_item(self, item_text):
        html = self.browser.page_source        
        menu = self.parser.extraer_items_menu(html)
        for key, val in menu.items():
            if key == item_text:
                js_call = val
                break
        if js_call:
            self.browser.execute_script(js_call)
    
    def get_parlamentary_list(self, origin):
        """returns the list of parlamentraries for the period 2008-2013
           @origin: S=senadores, D=diputados """
        try:
            period = 4
            #TODO: makte option selection with parameters
            #for origin and period
            self._call_menu_item(u'Parlamentarios por Período')#from side menu
            #formPreference:j_id16
            utils.make_webdriver_wait(By.ID, "formMain:cmdBuscarParlamentario", self.browser)
            utils.make_webdriver_wait(By.ID, 
                                      "formMain:idPeriodoLegislativo_input",
                                      self.browser)
            select_camara_element = self.browser.find_element_by_id("formMain:idOrigen_input")
            select_camara = Select(select_camara_element)
            select_camara.select_by_value(origin)
            select_periodo = self.browser.find_element_by_id("formMain:idPeriodoLegislativo_input")
            select = Select(select_periodo)
            select.select_by_index(period)
            self.browser.execute_script("PrimeFaces.ab({source:'formMain:cmdBuscarParlamentario'" +\
                                        ",update:'formMain'});return false;")        
            # wait for th class? Yes
            #WARNING: this is a bug
            # the css class .ui-widget-content.ui-datatable-even can be even or odd depending on the number of rows
            #use 'data-ri' instead of css ?
            utils.make_webdriver_wait(By.CSS_SELECTOR, 
                                      '.ui-widget-content.ui-datatable-even',
                                      self.browser)#".ui-datatable-header.ui-widget-header")
            number_of_rows = self.parser.number_of_rows_found(self.browser.page_source) #extraemos la cantidad de registros encontrados
            #esperamos por la aparicion del ultimo registro en base a su css
            last_row_id = "formMain:dataTable:%s:j_idt87" %(str(number_of_rows - 1))

            utils.make_webdriver_wait(By.ID, last_row_id, self.browser)
            return self.browser.page_source
        except Exception, err:
            #write to mongodb
            traceback.print_exc()
            error = {}
            error['method'] = 'buscar_comisiones_por_periodo'
            error['msg'] = err.message
            self.mongo_client.save_error(error)                    

    def get_member_projects(self, member_id):
        try:
            url='http://' + silpy_host + '/formulario/verProyectosParlamentario.pmf'\
                +'?q=verProyectosParlamentario%2F' + member_id
            self.browser.get(url)
            time.sleep(2)
            utils.wait_for_document_ready(self.browser)
            html = self.browser.page_source
            s = BeautifulSoup(html)
            if s.getText().find('UPS...') != -1:
                #load main page and needed cookes with it
                print 'La sesión de la consulta ha expirado!'
                self.browser.get('http://' + silpy_host + '/main.pmf')
                self.browser.get(url)
                #self.wait_for_document_ready(
                utils.wait_for_document_ready(self.browser)
                html = self.browser.page_source
            return html
        except Exception, err:
            #write to mongodb
            traceback.print_exc()
            error = {}
            error['method'] = 'get_member_projects'
            error['object'] = 'member'
            error['id'] =  member_id
            error['msg'] = err.message
            self.mongo_client.save_error(error)                   

    def buscar_comisiones_por_periodo(self, period):
        #este item prrobablemente deberia ser todo un ciclo de navegacion
        # 1- del menu principal llamar al js de Comisiones por Período
        # 2- seleccionar camara (senadores o diputados)
        # 3- seleccionar periodo
        # 4- buscar (click en el boton)
        # 5- Parser: Extraer datos del resultado de (4)
        # 6- Invocar a [Integrantes]
        # 7- Parser: Extraer datos del resultado de (6)
        # 8- Cerrar pop up (7) y repetir desde 6 con el siguiente item
        try:
            self._call_menu_item(u'Comisiones por Período')
            utils.make_webdriver_wait(By.ID, 
                                      "formMain:idPeriodoParlamentario_input",
                                      self.browser)
            select_camara_element = self.browser.find_element_by_id("formMain:idOrigen_input")
            select_camara = Select(select_camara_element)
            select_camara.select_by_index(1)#TODO: recibir el origen como parametro
            select_periodo_element = self.browser.find_element_by_id("formMain:idPeriodoParlamentario_input")
            select_periodo = Select(select_periodo_element)
            select_periodo.select_by_index(1)#TODO: recibir el periodo como parametro
            #se ejecuta la busqueda
            self.browser.execute_script("PrimeFaces.ab({source:'formMain:cmdBuscar',update:'formMain'});return false;")
            #esperar por el resultado
            rows_found = self.count_table_rows()
            waited_element = "formMain:dataTable:%s:j_idt101" % (rows_found)
            utils.make_webdriver_wait(By.ID, waited_element)
            #parseo de resultado
            comisiones = self.parser.extraer_comisiones_por_periodo(self.browser.page_source)
            #invocar a integrantes_js_call
            for c in comisiones:
                self.browser.execute_script(c['integrantes_js_call'])
                time.sleep(2)
                miembros = self.parser.extraer_miembros_por_comision(self.browser.page_source)
                c['members'] = miembros
            return comisiones
        except Exception, err:
            #write to mongodb
            traceback.print_exc()
            error = {}
            error['method'] = 'buscar_comisiones_por_periodo'
            error['object'] = 'bill'
            error['msg'] = err.message
            self.mongo_client.save_error(error)                    

    def list_bills_by_date(self, start, end):
        #dates are in dd/mm/yyyy format
        #<select id="formMain:idOrigen2_input" name="formMain:idOrigen2_input">
        #<option value="S" selected="selected">CAMARA DE SENADORES</option>
        #<option value="D">CAMARA DE DIPUTADOS</option>
        #<option value="A">---AMBAS CAMARAS---</option>
        #</select>
        self._call_menu_item(u'Leyes por Fecha')
        utils.make_webdriver_wait(By.ID, "formMain:idOrigen2_input", self.browser)
        select_camara_element = self.browser.find_element_by_id("formMain:idOrigen2_input")
        select_camara = Select(select_camara_element)
        select_camara.select_by_value("A")#both chambers
        #formMain:fechaDesde_input
        #formMain:fechaHasta_input
        textfiled_start_date = self.browser. \
                               find_element_by_id("formMain:fechaDesde_input")
        textfiled_start_date.send_keys(start)
        textfiled_end_date = self.browser. \
                             find_element_by_id("formMain:fechaHasta_input")
        textfiled_end_date.send_keys(end)
        #button_id= formMain:j_idt76
        search_button = self.browser.find_element_by_id("formMain:j_idt76")
        search_button.click()
        time.sleep(3)
        #formMain:dataTable:47:j_idt87
        number_of_rows = self.parser.number_of_rows_found(self.browser.page_source)
        if not number_of_rows:
            return None
        waited_element = 'formMain:dataTable:%s:j_idt87' %(str(number_of_rows-1))
        utils.make_webdriver_wait(By.ID, "formMain:idOrigen2_input", self.browser)
        result = []
        bills = self.parser.parse_bills_list_by_date(self.browser.page_source)
        for bill in bills:
            try:
                self.browser.execute_script(bill['js_call'])
                #we wait for papge ready + 5 seconds
                utils.wait_for_document_ready(self.browser)
                time.sleep(3)
                #extract bill data
                bill.update(self.parser.extract_project_details(self.browser.page_source))
                #press return button
                #j_idt61:j_idt64
                #print bill
                print self.browser.current_url
                reverse = self.browser.current_url[::-1]
                bill['id'] = reverse[0: reverse.index('F2%')][::-1]
                print "Bajando archivos del proyecto de ley %s" %(bill['info']['file'])
                bill = self.download_bill_files(bill)
                result.append(bill)
                return_button = self.browser.find_element_by_id("j_idt61:j_idt64")
                #save updated bills so far
                return_button.click()
            except Exception, err:
                #write to mongodb
                traceback.print_exc()
                error = {}
                error['method'] = 'list_bills_by_date'
                error['object'] = 'bill'
                #error['id'] = bill['id']
                error['msg'] = err.message
                self.mongo_client.save_error(error)
        return result

        
    #period = 2014-2013
    #origin = D(diputados), S(senadores)
    def list_sessions_by_period(self, origin, period):
        try:
            self._call_menu_item(u'Sesiones por Período')
            #self.wait_for_document_ready(
            utils.wait_for_document_ready(self.browser)
            utils.make_webdriver_wait(By.ID, "formMain:idOrigen_input", self.browser)
            select_camara_element = self.browser.find_element_by_id("formMain:idOrigen_input")
            select_camara = Select(select_camara_element)
            select_camara.select_by_value(origin)
            select_periodo_element = self.browser.find_element_by_id("formMain:idPeriodoParlamentario_input")
            select_periodo = Select(select_periodo_element)
            select_periodo.select_by_visible_text(period)
            self.browser.execute_script("PrimeFaces.ab({source:'formMain:cmdBuscar'" +\
                                        ",update:'formMain'});return false;")
            #self.wait_for_document_ready(
            utils.wait_for_document_ready(self.browser)
            number_of_rows = self.count_table_rows()
            #we wait for the button in the lat row 
            #Ex: formMain:dataTable:53:toggle

            last_row_id = "formMain:dataTable:%s:toggle" %(str(number_of_rows - 1))
            utils.make_webdriver_wait(By.ID, last_row_id, self.browser)
            return self.browser.page_source
        except Exception, err:
            #write to mongodb
            traceback.print_exc()
            error = {}
            error['method'] = 'list_sessions_by_period'
            error['object'] = 'bill'
            error['msg'] = err.message
            self.mongo_client.save_error(error)                    
    
    def download_attachment(self, origin, button_id, filename):
        #download attachments:
        # find button by id button_id': u'formMain:dataTableDetalle:3:j_idt113'
        # and click it
        button = self.browser.find_element_by_id(button_id)
        button.click()
        session_id = self.browser.get_cookie('JSESSIONID')['value']
        viewstate = self.parser.extract_viewstate(self.browser.page_source)
        #TODO async?
        utils.download_file(origin, session_id, viewstate, filename)
        
    
    def get_project_details(self, project_id, no_files=False):
        try:
            #obtiene una comision e invoca a la url:
            #GET http://silpy.congreso.gov.py/formulario/VerDetalleTramitacion.pmf?q=VerDetalleTramitacion%2F + project_id
            _url = "http://" + silpy_host + "/formulario/VerDetalleTramitacion.pmf"+ \
                   "?q=VerDetalleTramitacion%2F" + project_id
            self.browser.get(_url)
            time.sleep(2)
            print 'Getting ' +  _url
            bill = self.parser.extract_project_details(self.browser.page_source)
            bill['id'] = project_id
            #if true do not download files
            if no_files == True:
                return bill
            else:
                bill = self.download_bill_files(bill)
                return bill
        except Exception, err:
            #write to mongodb
            traceback.print_exc()
            error = {}
            error['type'] = 'get_project_details'
            error['object'] = 'bill'
            error['id'] = project_id
            error['msg'] = err.message
            error['url'] = _url
            self.mongo_client.save_error(error)

    def download_bill_files(self, bill):
        print "Downloading %s for bill id %s" %('documents', bill['id'])
        bill = self._download_bill_documents(bill)
        if False: #b0rk 'directives' in bill['sections_menu']:
            print "Downloading %s for bill id %s" %('directives', bill['id'])
            bill = self._download_bill_directives(bill)
        if 'resolutions_and_messages' in bill['sections_menu']:
            print "Downloading %s for bill id %s" %('resolutions and messages', bill['id'])
            bill = self._download_bill_resolutions_and_messages(bill)
        if 'laws_and_decrees' in bill['sections_menu']:
            print "Downloading %s for bill id %s" %('laws and decrees', bill['id'])
            bill = self._download_bill_laws_and_decrees(bill)
        return bill
            
    def _download_bill_directives(self, bill):
        menu_element = self.browser.find_element_by_link_text(
            bill['sections_menu']['directives']['text'])
        menu_element.click()
        time.sleep(2)
        index = 0
        #directives may have more than one file associated with each row
        while (index < len(bill['directives'])):
            directive = bill['directives'][index]
            print "downloading directive index: %s" %(directive['index'])
            if 'files' not in bill['directives'][index]:                 
                bill['directives'][index]['files'] = []
            download = True
            for button in directive['buttons']:
                try:
                    #unique hash to avoid downloading the same file more than once
                    idstr = bill['id'] + directive['date']+button['id']
                    hashid = hashlib.sha1(idstr.encode('utf-8')).hexdigest()
                    #if hashid is found on files we already have the file
                    if self.mongo_client.directive_exists(bill['id'], hashid):
                        download = False
                        print "File with hash %s already exists" %(hashid)
                    if download:
                        self.browser.find_element_by_id(button['id']).click()
                        time.sleep(1)
                        session_id = self.browser.get_cookie('JSESSIONID')['value']
                        viewstate = self.parser.extract_viewstate(self.browser.page_source)
                        path = utils.download_bill_directive(directive['index'],
                                                           button['index'],
                                                           bill['info']['file'],
                                                           viewstate,
                                                           session_id)
                    
                        bill['directives'][index]['files'].append({'id':hashid, 'path':path})                 
                except FileDownloadError, err:
                    #write to mongodb
                    traceback.print_exc()
                    error = {}
                    error['type'] = 'file_download'
                    error['object'] = 'bill'
                    error['id'] = bill['id']
                    error['msg'] = err.msg
                    error['curl_command'] = err.curl_command
                    error['downloader'] = '_download_bill_directives'
                    error['row'] = index
                    self.mongo_client.save_error(error)
                except Exception, err:
                    #write to mongodb
                    traceback.print_exc()
                    error = {}
                    error['method'] = '_download_bill_directives'
                    error['object'] = 'bill'
                    error['id'] =  bill['id']
                    error['msg'] = err.message
                    self.mongo_client.save_error(error)                    
            index += 1
        return bill
    
    def _download_bill_resolutions_and_messages(self, bill):
        menu_element = self.browser.find_element_by_link_text(
        bill['sections_menu']['resolutions_and_messages']['text'])
        menu_element.click()
        time.sleep(2)
        index = 0
        #these have more than one file associated with each row
        while (index < len(bill['resolutions_and_messages'])):
            obj = bill['resolutions_and_messages'][index]
            for button in obj['buttons']:
                try:
                    self.browser.find_element_by_id(button['id']).click()
                    time.sleep(1)
                    session_id = self.browser.get_cookie('JSESSIONID')['value']
                    viewstate = self.parser.extract_viewstate(self.browser.page_source)
                    button['path'] = utils.download_bill_resolutions_and_messages(index,
                                                               button['index'],
                                                               button['name'],
                                                               bill['info']['file'],
                                                               viewstate,
                                                               session_id)
                except FileDownloadError, err:
                    traceback.print_exc()
                    error = {}
                    error['type'] = 'file_download'
                    error['object'] = 'bill'
                    error['id'] = bill['id']
                    error['msg'] = err.msg
                    error['curl_command'] = err.curl_command
                    error['downloader'] = '_download_bill_resolutions_and_messages'
                    error['row'] = index
                    self.mongo_client.save_error(error)
                except Exception, err:
                    #write to mongodb
                    traceback.print_exc()
                    error = {}
                    error['method'] = '_download_bill_resolutions_and_messages'
                    error['object'] = 'bill'
                    error['id'] =  bill['id']
                    error['msg'] = err.message
                    self.mongo_client.save_error(error)                    
            bill['resolutions_and_messages'][index] = obj
            index += 1
        return bill
    
    def _download_bill_documents(self, bill):
        menu_element = self.browser.find_element_by_link_text(
        bill['sections_menu']['documents']['text'])
        menu_element.click()
        time.sleep(2)
        doc_index = 0
        while (doc_index < len(bill['documents'])):
            try:
                doc = bill['documents'][doc_index]
                self.browser.find_element_by_id(doc['button_id']).click()
                session_id = self.browser.get_cookie('JSESSIONID')['value']
                viewstate = self.parser.extract_viewstate(self.browser.page_source)
                doc['path'] = utils.download_bill_document(doc['button_id'],
                                                       doc['name'],
                                                       bill['info']['file'],
                                                       viewstate,
                                                       session_id)
            except FileDownloadError, err:
                    traceback.print_exc()
                    error = {}
                    error['type'] = 'file_download'
                    error['object'] = 'bill'
                    error['id'] = bill['id']
                    error['msg'] = err.msg
                    error['curl_command'] = err.curl_command
                    error['downloader'] = '_download_bill_resolutions_and_messages'
                    error['row'] = doc_index
                    self.mongo_client.save_error(error)
            except Exception, err:
                    #write to mongodb
                    traceback.print_exc()
                    error = {}
                    error['type'] = 'get_project_details'
                    error['object'] = 'bill'
                    error['id'] = bill['id']
                    error['msg'] = err.message
                    self.mongo_client.save_error(error)
            bill['documents'][doc_index] = doc
            doc_index += 1
        return bill

    def _download_bill_laws_and_decrees(self, bill):
        try:
            menu_element = self.browser.find_element_by_link_text(
                bill['sections_menu']['laws_and_decrees']['text'])
            menu_element.click()
            time.sleep(2)
            for law in bill['laws_and_decrees']:
                self.browser.find_element_by_id(law['button_id']).click()
                time.sleep(1)
                session_id = self.browser.get_cookie('JSESSIONID')['value']
                viewstate = self.parser.extract_viewstate(self.browser.page_source)
                law['filepath'] = utils.download_bill_law(law['name'],
                                                         bill['info']['file'],
                                                         viewstate,
                                                         session_id)
        except FileDownloadError, err:
            traceback.print_exc()
            error = {}
            error['type'] = 'file_download'
            error['object'] = 'bill'
            error['id'] = bill['id']
            error['msg'] = err.msg
            error['curl_command'] = err.curl_command
            error['downloader'] = '_download_bill_laws_and_decrees'
            self.mongo_client.save_error(error)
        except Exception, err:
            #write to mongodb
            traceback.print_exc()
            error = {}
            error['type'] = '_download_bill_laws_and_decrees'
            error['object'] = 'bill'
            error['id'] = bill['id']
            error['msg'] = err.message
            self.mongo_client.save_error(error)
        return bill

    def list_projects_by_committee(self, js_call):
        #TODO:invoke js_call from data dictionary
        #should this  be called when browsing projects by period?
        self.browser.execute_script(js_call)
        #count rows and wait for the last one
        number_of_rows = self.parser.number_of_rows_found(self.browser.page_source)
        last_row_id = 'formMain:dataTable:%s:acapite' %(number_of_rows - 1)    
        utils.make_webdriver_wait(By.ID,last_row_id, self.browser)
        return self.browser.page_source
            

#######################
### MainApp Section ###
#######################
from db.mongo_db import SilpyMongoClient
import urllib2

class SilpyScrapper(object):

    def __init__(self):   
        self.periods = ['2013-2014', '2014-2015']
        self.origins = ['D', 'S']
        self.navigator = SilpyNavigator()
        self.parser = SilpyHTMLParser()
        self.mongo_client = SilpyMongoClient()

    def close_navigator(self):
        self.navigator.close_driver()

    def get_members_data(self, origin):
        try:
            print 'ready to extract data'
            data = self.navigator.get_parlamentary_list(origin)
            rows = self.parser.parse_parlamentary_data(data)#member list

            index = 0
            while (index < len(rows)):
                row = rows[index]
                member_id = row['id']
                print 'procesando datos de: %s con id %s ' %(row['name'], member_id)
                html = self.navigator.get_member_projects(member_id)
                row['projects'] = self.parser.parse_projects_by_parlamentary(html)
                #download img
                filename = 'download/img2008_20013/'+ row['id'] + '.jpg'
                print 'downloading image: ' + row['id'] + '.jpg'
                urllib.urlretrieve(row['img'], filename)
                index += 1
                #save members collection here and then proceed to extract bills information
                #from what is saved in the data base
                if origin == 'S':
                    print "Guardando datos de Senador"
                    self.mongo_client.update_senador(row)
                elif origin == 'D':
                    print "Guardando datos de Diputado"
                    self.mongo_client.update_diputado(row)
            #self.update_members_bills_from_db(origin)
        except Exception, err:
            #write to mongodb
            traceback.print_exc()
            error = {}
            error['method'] = 'get_members_data'
            error['object'] = 'member'
            error['msg'] = err.message
            self.mongo_client.save_error(error)
            #write to mongodb
            traceback.print_exc()
            #self._log_error(err, bill['id'],'_download_bill_directives', index)            
        
    def update_members_bills_from_db(self, origin):
        #looks form members on the db and downloads their bills
        try:
            if origin == 'S':
                members  = self.mongo_client.get_all_senators()
            elif origin == 'D':
                members  = self.mongo_client.get_all_deputies()        
            for m in members: 
                print "Extrayendo proyectos de %s " %(m['name'])
                self._update_bills(m['projects'])
        except Exception, err:
            print "WARNING: Improve Exception handling."
            #write to mongodb
            traceback.print_exc()
            error = {}
            error['method'] = 'update_members_bills_from_db'
            error['object'] = 'bill'
            error['id'] = project['id']
            error['msg'] = err.message
            self.mongo_client.save_error(error)
 
    def download_all_bills(self, new=False, no_files=False):
        #if new = True download only projects
        #not found in db.projects collection
        try:
            #download all bills from both chambers
            #TODO: new = True, download only new bills
            all_projects_ids = []
            all_projects = {}
            db = self.mongo_client.db
            senadores = db.senadores.find()
            for s in senadores:
                for p in s['projects']:
                    all_projects[p['id']] = p
                    all_projects_ids.append(p['id'])
            diputados = db.diputados.find()
            for d in diputados:
                if 'projects' in d:
                    for p in d['projects']:
                        all_projects[p['id']] = p
                        all_projects_ids.append(p['id'])
            unique_ids = list(set(all_projects_ids))
            #projects = db.projects.find({'id': {'$exists': True, '$in':unique_ids}})
            if new:
                #TODO: remove from the unique list projects that are in db.projects
                # get all projects from members that are on the unique list
                downloaded_projects = list(db.projects.find({},{'_id':0,'id': 1}))
                for dp in downloaded_projects:
                    "Project with id %s already downloaded." %dp['id'] 
                    del all_projects[dp['id']]
                    
            print 'Downloading %s and their related files.' %(len(all_projects))
            self._update_bills(all_projects.values(), no_files)
        except Exception, err:
            print "WARNING: Improve Exception handling."
            traceback.print_exc()


    def update_bills(self):
        #gets bills that has been updated
        #searching bill by a range of date brings all those that were in some way updated
        #it does not brings by ordered by entry_date
        #Mechanism:
        # 1- Look bills by a range of date,
        #   the first time we can get all bills within a year is ideal,
        #   then use from last update date to today.    
        # 2- List and iterate over them.
        # 3- create or update "last_bills" collection
        # updated_bill has the last updated date
        # and the bills from that date
        
        d = datetime.datetime.utcnow()
        updated_bills = self.mongo_client.db.updated_bills.find_one()
        if not updated_bills:
            #create new updated bill from the beginning of this year
            start = "01/01/%d" %(d.year)
        else:
            start = updated_bills['last_update']
        
        end = d.strftime("%d/%m/%Y")
        bills = self.navigator.list_bills_by_date(start, end)
        updated_bills = {'id': 1}
        updated_bills['last_update'] = end
        last_bills = {}
        last_bills['start_date'] = start
        last_bills['end_date'] = end
        last_bills['bills'] = bills
        updated_bills[end] = last_bills
        self.mongo_client.db.updated_bills.update({'id':1},
                                                   {'$set':updated_bills},
                                                   True)

    def _update_bills(self, projects, no_files=False):
        #Recieves a list of bills, from the data base or
        #from scrapping and updates existing records in the DB.        
        index = 0
        while(index < len(projects)):
            try:
                project = projects[index]
                if 'id' not in project:
                    print 'project id not found'
                else:
                    print "id de proyecto " + project['id']                    
                    self.mongo_client = SilpyMongoClient()
                    project.update(self.navigator.get_project_details(project['id'], no_files))
                    self.mongo_client.upsert_project(project)
                    #navigator.close_driver()
            except Exception, err:
                self.navigator.close_driver()
                #write to mongodb
                traceback.print_exc()
                error = {}
                error['method'] = '_update_bills'
                error['object'] = 'bill'
                error['id'] = project['id']
                error['msg'] = err.message
                self.mongo_client.save_error(error)
            index +=1
            
    def get_commiittees_by_period(self):
         periodo = '2014-2015'
         comisiones_periodo = self.navigator.buscar_comisiones_por_periodo()
         self.mongo_client.save_comisiones_por_periodo(periodo, comisiones_periodo)
        
    def get_sessions_by_period(self):
        #TODO
        #for period in self.periods:
        period = '2014-2015'
        origin='D'
        data = self.navigator.list_sessions_by_period(origin, period)
        session_list = self.parser.parsear_lista_sessiones(data)
        for s in session_list:
           #call and extract anexos: anexos_js_call
           #print s['index']+ ' - - '  +s['anexos_js_call']
           self.navigator.browser.execute_script(s['anexos_js_call'])
           #wait for the popup to load
           #formMain:dataTableDetalle:0:j_idt113 the id of the first button
           utils.make_webdriver_wait(By.ID, 
                                     "formMain:dataTableDetalle:0:j_idt113", 
                                     self.navigator.browser)
           #pass the resulting html to attachment extractor
           attachments = self.parser.extract_session_attachment(self.navigator.browser.page_source)
           #download attachments:
           # find button by button_id : u'formMain:dataTableDetalle:3:j_idt113'
           # and click it
           # for attachment in attachments:
           #     print attachment
           #     self.navigator.download_attachment(origin, 
           #                                        attachment['button_id'], 
           #                                        attachment['nombre'])
           #find and call button_id
           #call and extract proyectos

