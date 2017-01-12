#!/usr/bin/env python
import json
import time
import xml.etree.ElementTree as ET
import argparse
import sys
import subprocess

import requests
from decimal import Decimal

from gomatic.gocd.pipelines import Pipeline, PipelineGroup
from gomatic.gocd.agents import Agent
from gomatic.xml_operations import Ensurance, PossiblyMissingElement, move_all_to_end, prettify


class GoCdConfigurator(object):
    def __init__(self, host_rest_client):
        self.__host_rest_client = host_rest_client
        self.__set_initial_config_xml()

    def __set_initial_config_xml(self):
        initial_config, self._initial_md5 = self.__current_config_response()
        self.__initial_config = initial_config.encode('ascii', errors='xmlcharrefreplace')
        self.__xml_root = ET.fromstring(self.__initial_config)

    @property
    def current_config(self):
        return self.__current_config_response()[0]

    def __current_config_response(self):
        config_url = "/go/admin/restful/configuration/file/GET/xml"
        response = self.__host_rest_client.get(config_url)

        if response.status_code != 200:
            raise Exception("Failed to get {} status {}\n:{}".format(config_url, response.status_code, response.text))
        return response.text, response.headers['x-cruise-config-md5']

    def reorder_elements_to_please_go(self):
        move_all_to_end(self.__xml_root, 'pipelines')
        move_all_to_end(self.__xml_root, 'templates')
        move_all_to_end(self.__xml_root, 'environments')
        move_all_to_end(self.__xml_root, 'agents')

        for group in self.pipeline_groups:
            for pipeline in group.pipelines:
                pipeline.reorder_elements_to_please_go()
        for template in self.templates:
            template.reorder_elements_to_please_go()

    @property
    def config(self):
        self.reorder_elements_to_please_go()
        return ET.tostring(self.__xml_root, 'utf-8')


    @property
    def pipeline_groups(self):
        return [PipelineGroup(e, self) for e in self.__xml_root.findall('pipelines')]

    def __ensure_pipeline_group(self, group_name):
        pipeline_group_element = Ensurance(self.__xml_root).ensure_child_with_attribute("pipelines", "group", group_name)
        return PipelineGroup(pipeline_group_element.element, self)

    def ensure_replacement_of_pipeline_group(self, group_name):
        group = self.__ensure_pipeline_group(group_name)
        group.make_empty()
        return group

    def ensure_removal_of_pipeline_group(self, group_name):
        matching = [g for g in self.pipeline_groups if g.name == group_name]
        for group in matching:
            self.__xml_root.remove(group.element)
        return self

    @property
    def agents(self):
        return [Agent(e) for e in PossiblyMissingElement(self.__xml_root).possibly_missing_child('agents').findall('agent')]

    def ensure_removal_of_agent(self, hostname):
        matching = [agent for agent in self.agents if agent.hostname == hostname]
        for agent in matching:
            Ensurance(self.__xml_root).ensure_child('agents').element.remove(agent._element)
        return self


    @property
    def templates(self):
        return [Pipeline(e, 'templates') for e in PossiblyMissingElement(self.__xml_root).possibly_missing_child('templates').findall('pipeline')]

    def __ensure_template(self, template_name):
        pipeline_element = Ensurance(self.__xml_root).ensure_child('templates').ensure_child_with_attribute('pipeline', 'name', template_name).element
        return Pipeline(pipeline_element, 'templates')

    def ensure_replacement_of_template(self, template_name):
        template = self.__ensure_template(template_name)
        template.make_empty()
        return template

    def ensure_removal_of_template(self, template_name):
        matching = [template for template in self.templates if template.name == template_name]
        root = Ensurance(self.__xml_root)
        templates_element = root.ensure_child('templates').element
        for template in matching:
            templates_element.remove(template.element)
        if len(self.templates) == 0:
            root.element.remove(templates_element)
        return self

    @property
    def has_changes(self):
        return prettify(self.__initial_config) != prettify(self.config)

    def save_updated_config(self, save_config_locally=False, dry_run=False):
        config_before = prettify(self.__initial_config)
        config_after = prettify(self.config)
        if save_config_locally:
            open('config-before.xml', 'w').write(config_before.encode('utf-8'))
            open('config-after.xml', 'w').write(config_after.encode('utf-8'))

            def has_kdiff3():
                try:
                    return subprocess.call(["kdiff3", "-version"]) == 0
                except:
                    return False

            if dry_run and config_before != config_after and has_kdiff3():
                subprocess.call(["kdiff3", "config-before.xml", "config-after.xml"])

        data = {
            'xmlFile': self.config,
            'md5': self._initial_md5
        }

        if not dry_run and config_before != config_after:
            self.__host_rest_client.post('/go/admin/restful/configuration/file/POST/xml', data)
            self.__set_initial_config_xml()


class HostRestClient(object):
    def __init__(self, host):
        self.__host = host

    def __repr__(self):
        return 'HostRestClient("%s")' % self.__host

    def __path(self, path):
        return ('http://%s' % self.__host) + path

    def get(self, path):
        result = requests.get(self.__path(path))
        count = 0
        while ((result.status_code == 503) or (result.status_code == 504)) and (count < 5):
            result = requests.get(self.__path(path))
            time.sleep(1)
            count += 1
        return result

    def post(self, path, data):
        url = self.__path(path)
        result = requests.post(url, data)
        if result.status_code != 200:
            try:
                result_json = json.loads(result.text.replace("\\'", "'"))
                message = result_json.get('result', result.text)
                raise RuntimeError("Could not post config to Go server (%s) [status code=%s]:\n%s" % (url, result.status_code, message))
            except ValueError:
                raise RuntimeError("Could not post config to Go server (%s) [status code=%s] (and result was not json):\n%s" % (url, result.status_code, result))