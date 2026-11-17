
def make_project(client):
    response = client.post('/api/v1/projects/', json={
        'name': 'Projeto teste', 'code': 'TEST-API', 'start_date': '2026-01-01', 'end_date': '2026-01-20'
    })
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_project_activity_wbs_and_cpm_flow(client):
    project_id = make_project(client)
    wbs = client.post('/api/v1/activities/wbs', json={
        'project_id': project_id, 'name': 'Fundações', 'code': '1.1'
    })
    assert wbs.status_code == 201, wbs.text
    wbs_id = wbs.json()['id']

    a = client.post('/api/v1/activities/', json={
        'project_id': project_id, 'wbs_id': wbs_id, 'name': 'Escavação', 'code': 'ESC-01', 'duration': 3
    })
    b = client.post('/api/v1/activities/', json={
        'project_id': project_id, 'wbs_id': wbs_id, 'name': 'Concretagem', 'code': 'CON-01', 'duration': 4
    })
    assert a.status_code == 201 and b.status_code == 201
    aid, bid = a.json()['id'], b.json()['id']

    relation_1 = client.post('/api/v1/activities/precedences', json={
        'predecessor_id': aid, 'successor_id': bid, 'relation_type': 'FS', 'lag': 0
    })
    relation_2 = client.post('/api/v1/activities/precedences', json={
        'predecessor_id': aid, 'successor_id': bid, 'relation_type': 'SS', 'lag': 0
    })
    assert relation_1.status_code == 201 and relation_2.status_code == 201

    calculated = client.post(f'/api/v1/activities/project/{project_id}/calculate-cpm')
    assert calculated.status_code == 200, calculated.text
    body = calculated.json()
    assert body['deadline_feasible'] is True
    assert body['activities'][str(bid)]['es'] == 3
    assert body['activities'][str(bid)]['ef'] == 7

    listed = client.get(f'/api/v1/activities/project/{project_id}/wbs')
    assert listed.status_code == 200 and len(listed.json()) == 1


def test_precedence_rejects_cross_project_and_cycles(client):
    p1 = make_project(client)
    p2 = client.post('/api/v1/projects/', json={'name':'Outro','code':'TEST-API-2'}).json()['id']
    a = client.post('/api/v1/activities/', json={'project_id':p1,'name':'A','code':'A','duration':1}).json()['id']
    b = client.post('/api/v1/activities/', json={'project_id':p1,'name':'B','code':'B','duration':1}).json()['id']
    c = client.post('/api/v1/activities/', json={'project_id':p2,'name':'C','code':'C','duration':1}).json()['id']
    assert client.post('/api/v1/activities/precedences', json={'predecessor_id':a,'successor_id':c}).status_code == 400
    assert client.post('/api/v1/activities/precedences', json={'predecessor_id':a,'successor_id':b}).status_code == 201
    assert client.post('/api/v1/activities/precedences', json={'predecessor_id':b,'successor_id':a}).status_code == 400


def test_project_duplication_copies_wbs_activities_and_precedences(client):
    project_id = make_project(client)
    wbs_id = client.post('/api/v1/activities/wbs', json={'project_id':project_id,'name':'Estrutura','code':'2'}).json()['id']
    a = client.post('/api/v1/activities/', json={'project_id':project_id,'wbs_id':wbs_id,'name':'Pilar','code':'PIL','duration':2}).json()['id']
    b = client.post('/api/v1/activities/', json={'project_id':project_id,'wbs_id':wbs_id,'name':'Viga','code':'VIG','duration':3}).json()['id']
    client.post('/api/v1/activities/precedences', json={'predecessor_id':a,'successor_id':b,'relation_type':'FS','lag':1})
    duplicate = client.post(f'/api/v1/projects/{project_id}/duplicate')
    assert duplicate.status_code == 201, duplicate.text
    duplicate_id = duplicate.json()['id']
    assert len(client.get(f'/api/v1/activities/project/{duplicate_id}/wbs').json()) == 1
    duplicated_activities = client.get(f'/api/v1/activities/project/{duplicate_id}').json()
    assert len(duplicated_activities) == 2
    duplicated_precedences = client.get(f'/api/v1/activities/project/{duplicate_id}/precedences').json()
    assert len(duplicated_precedences) == 1


def test_wbs_cannot_be_moved_under_its_descendant(client):
    project_id = make_project(client)
    parent = client.post('/api/v1/activities/wbs', json={'project_id':project_id,'name':'Pai','code':'1'}).json()['id']
    child = client.post('/api/v1/activities/wbs', json={'project_id':project_id,'name':'Filho','code':'1.1','parent_id':parent}).json()['id']
    response = client.put(f'/api/v1/activities/wbs/{parent}', json={'parent_id':child})
    assert response.status_code == 400


def test_contract_deadline_is_passed_to_cpm_endpoint(client):
    project_id = make_project(client)  # deadline is 19 days
    client.post('/api/v1/activities/', json={'project_id':project_id,'name':'Longa','code':'LONG','duration':25})
    result = client.post(f'/api/v1/activities/project/{project_id}/calculate-cpm')
    assert result.status_code == 200
    body = result.json()
    assert body['deadline_feasible'] is False
    assert body['activities']['1']['tf'] == -6


def test_activity_ifc_element_association_is_persisted(client, db):
    from app.models.ifc import IfcModelModel, IfcElementModel
    project_id = make_project(client)
    activity_id = client.post('/api/v1/activities/', json={'project_id':project_id,'name':'Alvenaria','code':'ALV','duration':4}).json()['id']
    model = IfcModelModel(project_id=project_id, filename='modelo.ifc', file_path='/tmp/modelo.ifc', status='completed', progress=100)
    db.add(model); db.commit(); db.refresh(model)
    element = IfcElementModel(model_id=model.id, global_id='0ABCDEF123456789', name='Parede 01', ifc_type='IfcWall')
    db.add(element); db.commit(); db.refresh(element)
    linked = client.post(f'/api/v1/activities/{activity_id}/ifc-elements', json={'ifc_element_id':element.id})
    assert linked.status_code == 201, linked.text
    assert linked.json()['global_id'] == '0ABCDEF123456789'
    listed = client.get(f'/api/v1/activities/{activity_id}/ifc-elements')
    assert listed.status_code == 200 and listed.json()[0]['global_id'] == '0ABCDEF123456789'
    unlinked = client.delete(f'/api/v1/activities/{activity_id}/ifc-elements/{element.id}')
    assert unlinked.status_code == 204
    assert client.get(f'/api/v1/activities/{activity_id}/ifc-elements').json() == []
