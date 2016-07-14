#!/usr/bin/env python3

import argparse
import json
import os
import re
from urllib.request import urlopen
import urllib

def loadf(filename):
    try:
        with open(filename,'r') as f:
            return json.load(f)
    except:
        return None

def dumpf(obj, filename):
    try:
        with open(filename,'w') as f:
            return json.dump(obj,f,sort_keys=True,indent=4)
    except:
        return None

def delete_empty_races(root_dir='', start=0, stop=999999):
    for i in range(start,stop):
        try:
            filename = get_filename(id=id,root_dir=root_dir)
            race = loadf(filename)
            if not race or not race.get('results',[]):
                print('Race empty; deleting file {filename}'.format(filename=filename))
                os.remove(filename)
            else:
                print('Keeping race {name}'.format(name=race['name']))
        except Exception as e:
            pass

def download_and_cache(id, root_dir=''):
    try:
        name, date, results = download_race_page(id)
        cache_results(id=id, race_name=name, race_date=date, results=results, root_dir=root_dir)
        print("Cached results for race {id} ({name})".format(id=id, name=name))
    except Exception as e:
        print(str(e))

def download_race_page(id):
    raw_page = urlopen('http://ultrasignup.com/results_event.aspx?did={id}'.format(id=id)).read().decode('utf-8')
    throw_if_invalid(id=id, raw_page=raw_page)
    name = pull_race_name(raw_page)
    date = pull_race_date(raw_page)
    results = json.loads(urlopen('http://ultrasignup.com/service/events.svc/results/{id}/json'.format(id=id)).read().decode('utf-8'))
    if not results:
        raise RuntimeError("Results for race {id} were empty.".format(id=id))
    return name, date, results

def cache_results(id, race_name, race_date, results, root_dir=''):
    data = {
        'id':str(id),
        'name':race_name,
        'date':race_date,
        'results':results
        }
    filename = get_filename(id=id,root_dir=root_dir)
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2, sort_keys=True)

def pull_race_name(raw_page):
    lines = raw_page.split('\n')
    next_line = False
    for line in lines:
        if next_line:
            return line.strip()[:-10]
        if line.strip().endswith('<title>'):
            next_line = True
    return None

def pull_race_date(raw_page):
    lines = raw_page.split('\n')
    for line in lines:
        if 'lblDate' in line:
            return line.strip()[38:-7]
    return ''

def throw_if_invalid(id, raw_page):
    if 'topten_age'.format(id=id) not in raw_page:
        raise RuntimeError('Race {id} not found.'.format(id=id))

def get_filename(id, root_dir):
    return root_dir + 'race-{id}.json'.format(id=id)

def get_year(name):
    return name[:4]

def load_cache(id, root_dir=''):
    filename = get_filename(id, root_dir)
    return loadf(filename)

def dump_runner_map(start=0,stop=99999,root_dir='',analysis_dir=''):
    race_list = {}
    runner_list = set()
    for i in range(start,stop):
        race = load_cache(i, root_dir=root_dir)
        if race:
            name = race['name']
            year = name[:4]
            title = name[5:]
            years = race_list.get(title,{})
            runners = []
            for runner in  [r for r in race['results'] if int(r['age']) > 5]:
                age = runner['age']
                birth_year = int(year)-int(age)
                id = clean(runner, birth_year)
                runner_list.add(id)
                runners += [id]
            years[year] = runners
            race_list[title] = years

    runner_map = {}
    for runner in runner_list:
        person = '/'.join(runner.split('/')[0:3])
        birth_year = runner.split('/')[3]
        birth_years = runner_map.get(person, [])
        birth_years += [birth_year]
        runner_map[person] = birth_years
        if birth_years[0] == 'F':
            print(runner)
    runner_year_map = {r:get_birth_year_map(runner_map[r]) for r in runner_map.keys()}
    flat_map = {}
    for r in runner_year_map:
        for k in runner_year_map[r]:
            flat_map[r+'/'+str(k)] = r+'/'+str(runner_year_map[r][k])
    dumpf(flat_map,analysis_dir+'runner_map.json')

def clean_name(name):
    return name.replace('/','-').replace(' ','_')

def clean(runner, birth_year=None):
    cleaned = clean_name(runner['firstname']) + '/' + clean_name(runner['lastname']) + '/' + clean_name(runner['gender'])
    if birth_year:
        cleaned = cleaned + '/' + str(birth_year)
    return cleaned

def generate_race_files(start=0,stop=99999,root_dir='',analysis_dir='',individual_files=False):
    runner_map = loadf(analysis_dir+'runner_map.json')
    race_list = {}
    for i in range(start, stop):
        race = load_cache(i, root_dir=root_dir)
        if race:
            name = race['name']
            year = name[:4]
            title = name[5:]
            years = race_list.get(title,{})
            runners = []
            updated_results = []
            for runner in  [r for r in race['results'] if int(r['age']) > 5]: # filter out the ones who didn't enter age, as they're tough to track
                age = runner['age']
                birth_year = int(year)-int(age)
                id = clean(runner, birth_year)
                res = runner
                res['id'] = runner_map[id]
                updated_results += [res]
            years[year] = updated_results
            race_list[title] = years
    dumpf(race_list,analysis_dir+'race_list.json')
    if individual_files:
        for r in race_list:
            name = clean_name(r)
            years = race_list[r]
            data = {
                'name':r,
                'years':years
                }
            dumpf(data, analysis_dir+name+'.race.json')

def generate_runner_files(start=0,stop=99999,root_dir='',analysis_dir='',individual_files=False):
    runner_map = loadf(analysis_dir+'runner_map.json')
    unique_runners = set(runner_map[k] for k in runner_map)
    runner_results = {}
    race_list = loadf(analysis_dir+'race_list.json')
    for name in race_list:
        years = race_list[name]
        for year in years:
            for runner in years[year]:
                id = runner['id']
                this_guy = runner_results.get(id, {})
                all_years = this_guy.get(name, {})
                all_years[year] = runner
                this_guy[name] = all_years
                runner_results[id] = this_guy
    dumpf(runner_results,analysis_dir+'runner_results.json')
    if individual_files:
        for r in runner_results:
            name = clean_name(r)
            data = {
                'id':r,
                'years':runner_results[r]
                }
            dumpf(data, analysis_dir+name+'.runner.json')

def get_birth_year_map(years):
    years.sort()
#    print(years)
    prev_year = int(years[0])
    canon_year = prev_year
    year_map = {prev_year:canon_year}
    for i in range(len(years)-1):
        j = i+1
        cur_year = int(years[j])
        if cur_year <= prev_year+2:
            pass
        else:
            canon_year = cur_year
        year_map[cur_year] = canon_year
    return year_map

def find_competitors(id, race_list, runner_results):
    my_races = runner_results[id]
    competitors = set()
    for race in my_races:
        for year in my_races[race]:
            competitors.update(r['id'] for r in race_list[race][year] if r['id'] != id)
    return competitors

def main():
    root_dir='/Users/norums/personal/repos/goatmeister/races/'
    analysis_dir='/Users/norums/personal/repos/goatmeister/analysis/'
#     dump_runner_map(start=0,stop=50000,root_dir=root_dir,analysis_dir=analysis_dir)
#     generate_race_files(start=0,stop=50000,root_dir=root_dir,analysis_dir=analysis_dir)
#     generate_runner_files(start=0,stop=50000,root_dir=root_dir,analysis_dir=analysis_dir)
    runner_results = loadf(analysis_dir+'runner_results.json')
    race_list = loadf(analysis_dir+'race_list.json')
#     id='tj/Pitts/M/1987'
    id='william/Land/M/1948'
    print(find_competitors(id, race_list, runner_results))
#     parse_and_cache_clean(start=0,stop=50000,root_dir=root_dir)
#     delete_empty_races(root_dir=root_dir, start=12930, stop=29000)
#     for i in range(40000, 50000):
#         download_and_cache(i, root_dir='/Users/norums/personal/repos/goatmeister/races/')

if __name__ == '__main__':
    main()
