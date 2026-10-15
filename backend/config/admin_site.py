from django.contrib.admin import AdminSite


class EveAdminSite(AdminSite):
    enable_nav_sidebar = False

    def each_context(self,request):
        from .admin_metrics import totals
        context=super().each_context(request)
        if request.user.is_authenticated and request.user.is_staff:
            context['admin_totals']=totals(request.user)
            context['can_view_betting_status']=request.user.has_perm('sportsfeed.view_demoslip') or request.user.has_perm('sportsfeed.change_demoslip')
        return context

    def get_app_list(self, request, app_label=None):
        apps = super().get_app_list(request, app_label)
        if app_label:
            return apps
        support_labels = {'notices', 'inquiries', 'board'}
        from django.urls import reverse
        engine=next((app for app in apps if app['app_label']=='sportsfeed'),None)
        games=next((app for app in apps if app['app_label']=='catalog'),None)
        if engine:
            engine['name']='등록엔진'
            groups=[('OddsHarvester',{'HarvesterSnapshot','HarvesterJob'}),('OddsParsing',{'OddsPortalSnapshot','OddsPortalCollectionJob'}),('The Odds API',{'FeedSnapshot'})]
            registration={name for _,names in groups for name in names}
            moved=[model for model in engine['models'] if model['object_name'] not in registration]
            engine['models']=[model for model in engine['models'] if model['object_name'] in registration]
            labels={'FeedSnapshot':'API 수집·갱신','HarvesterSnapshot':'수집 실행','HarvesterJob':'수집 이력','OddsPortalSnapshot':'수집 실행','OddsPortalCollectionJob':'수집 이력'}
            for model in engine['models']: model['name']=labels.get(model['object_name'],model['name'])
            engine['menu_groups']=[{'name':name,'models':[model for model in engine['models'] if model['object_name'] in names]} for name,names in groups]
            engine['menu_groups']=[group for group in engine['menu_groups'] if group['models']]
            if any(model['object_name']=='HarvesterSnapshot' for model in engine['models']):
                inplay={'name':'Inplay','object_name':'InplayEngine','admin_url':reverse('admin:sportsfeed_inplay_collect'),'view_only':True,'perms':{'view':True}}
                engine['models'].append(inplay)
                engine['menu_groups'].append({'name':'Inplay','models':[{**inplay,'name':'수집 실행'}]})
            if moved:
                if not games:
                    games={'name':'게임 관리','app_label':'catalog','app_url':engine['app_url'],'has_module_perms':True,'models':[]}
                    apps.append(games)
                for model in moved:
                    if model['object_name']=='DemoLeg': model['name']='배팅 경기별 정산'
                games['models'].extend(moved)
            if not engine['models']: apps.remove(engine)
        for app in apps:
            if app['app_label'] == 'catalog':
                if not (request.user.has_perm('catalog.view_game') or request.user.has_perm('catalog.change_game')): continue
                app['models'].append({'name': '경기·배당 전체 조회', 'object_name': 'MatchOdds',
                    'admin_url': reverse('admin:catalog_game_odds'), 'view_only': True,
                    'perms': {'view': True}})
                app['models'].append({'name': '경기결과', 'object_name': 'MatchResults',
                    'admin_url': reverse('admin:catalog_game_odds') + '?status=results',
                    'view_only': True, 'perms': {'view': True}})
        support = [app for app in apps if app['app_label'] in support_labels]
        if support:
            models = [model for app in support for model in app['models']]
            apps = [app for app in apps if app['app_label'] not in support_labels]
            apps.append({
                'name': '고객센터', 'app_label': 'customer_support',
                'app_url': support[0]['app_url'],
                'has_module_perms': True, 'models': models,
            })
        return apps
