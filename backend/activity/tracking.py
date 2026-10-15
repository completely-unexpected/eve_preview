import hashlib
import json
import re
import sys
from contextvars import ContextVar
from django.apps import apps
from django.db import connections
from django.db.backends.signals import connection_created
from django.db.models.signals import post_save, post_delete, m2m_changed

context = ContextVar('activity_context', default=None)
busy = ContextVar('activity_busy', default=False)
PROJECT_APPS = {'accounts','wallet','sportsfeed','attendance','board','events','catalog','inquiries','notices'}
SECRET = re.compile(r'password|token|secret|cookie|session|credential|referral_code|fingerprint|account_number|phone', re.I)


def clean(value, key=''):
    if SECRET.search(key): return '[보호된 값]'
    if isinstance(value, dict): return {str(k):clean(v,str(k)) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [clean(v) for v in value]
    if value is None or isinstance(value,(str,int,float,bool)): return value
    return str(value)


def compact(value):
    encoded=json.dumps(value,ensure_ascii=False,default=str)
    if len(encoded)>6000:
        return {'summary':'큰 데이터 변경', 'characters':len(encoded), 'sha256':hashlib.sha256(encoded.encode()).hexdigest()}
    return value


def record(action, model='', object_id='', changes=None, status=None):
    if busy.get(): return
    token=busy.set(True)
    try:
        connection=connections['default']
        if not getattr(connection,'_activity_has_table',False):
            if 'activity_activitylog' not in connection.introspection.table_names(): return
            connection._activity_has_table=True
        from .models import ActivityLog
        actor=context.get() or {'actor':'자동 작업: '+(sys.argv[1] if len(sys.argv)>1 and not sys.argv[1].startswith('-') else 'Django'), 'actor_kind':'system'}
        ActivityLog.objects.create(**actor,action=action,target_model=model,target_id=str(object_id)[:100],changes=compact(clean(changes or {})),status_code=status)
    finally:
        busy.reset(token)


def snapshot(instance):
    return {field.name:clean(getattr(instance,field.attname),field.name) for field in instance._meta.concrete_fields}


def field_value(field,value):
    if SECRET.search(field.name):
        return hashlib.sha256(str(value).encode()).hexdigest()
    if field.get_internal_type()=='JSONField' and isinstance(value,str):
        try: value=json.loads(value)
        except (TypeError,ValueError): pass
    return clean(value,field.name)


def created(sender,instance,created,raw=False,**kwargs):
    if created and not raw and sender._meta.app_label in PROJECT_APPS:
        record('create',sender._meta.label,instance.pk,{'after':snapshot(instance)})


def deleted(sender,instance,**kwargs):
    if sender._meta.app_label in PROJECT_APPS:
        record('delete',sender._meta.label,instance.pk,{'before':snapshot(instance)})


def relation(sender,instance,action,pk_set,reverse,**kwargs):
    if action.startswith('post_') and instance._meta.app_label in PROJECT_APPS:
        record('relation',instance._meta.label,instance.pk,{'operation':action,'relation':sender._meta.label,'related_ids':sorted(pk_set or []),'reverse':reverse})


def write_wrapper(execute,sql,params,many,query_context):
    if busy.get(): return execute(sql,params,many,query_context)
    match=re.match(r'^UPDATE\s+["`]?([\w]+)["`]?\s+SET\s+',sql,re.I)
    if not match: return execute(sql,params,many,query_context)
    models={model._meta.db_table:model for model in apps.get_models() if model._meta.app_label in PROJECT_APPS}
    model=models.get(match[1])
    if not model: return execute(sql,params,many,query_context)
    connection=query_context['connection']
    # Compare sensitive values via transient digests; never persist their contents.
    fields=list(model._meta.concrete_fields)
    quote=connection.ops.quote_name
    columns=','.join(quote(field.column) for field in fields)
    tail=sql[match.end():]
    parts=re.split(r'\s+WHERE\s+',tail,maxsplit=1,flags=re.I)
    where=' WHERE '+parts[1] if len(parts)>1 else ''
    where_params=(params or ())[parts[0].count('%s'):] if not many else ()
    if many: return execute(sql,params,many,query_context)
    def read():
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT {columns} FROM {quote(model._meta.db_table)}'+where,where_params)
            return {str(row[[f.primary_key for f in fields].index(True)]):{field.name:field_value(field,value) for field,value in zip(fields,row)} for row in cursor.fetchall()}
    before=read()
    result=execute(sql,params,many,query_context)
    # Read by original primary keys even when an UPDATE changes the WHERE fields.
    if before:
        pk=quote(model._meta.pk.column)
        after={}
        for object_id in before:
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT {columns} FROM {quote(model._meta.db_table)} WHERE {pk} = %s',[object_id])
                row=cursor.fetchone()
                if row: after[object_id]={field.name:field_value(field,value) for field,value in zip(fields,row)}
        for object_id,old in before.items():
            new=after.get(object_id,{})
            changes={key:{'before':old.get(key),'after':new.get(key)} for key in old.keys()|new.keys() if old.get(key)!=new.get(key)}
            if changes: record('update',model._meta.label,object_id,changes)
    return result


def install_connection(sender=None,connection=None,**kwargs):
    connection._activity_has_table=False
    if write_wrapper not in connection.execute_wrappers: connection.execute_wrappers.append(write_wrapper)


def install():
    post_save.connect(created,dispatch_uid='activity_created')
    post_delete.connect(deleted,dispatch_uid='activity_deleted')
    m2m_changed.connect(relation,dispatch_uid='activity_relation')
    connection_created.connect(install_connection,dispatch_uid='activity_connection')
    for connection in connections.all(): install_connection(connection=connection)
