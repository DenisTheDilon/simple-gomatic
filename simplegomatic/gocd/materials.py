from xml.etree import ElementTree as ET
from simplegomatic.mixins import CommonEqualityMixin
from simplegomatic.xml_operations import ignore_patterns_in


def Materials(element):
    """
    Material instance initializer.
    """
    if element.tag == "git":
        branch = element.attrib.get('branch', None)
        material_name = element.attrib.get('materialName', None)
        polling = element.attrib.get('autoUpdate', 'true') == 'true'
        destination_directory = element.attrib.get('dest', None)
        return GitMaterial(element.attrib['url'],
                           branch=branch,
                           material_name=material_name,
                           polling=polling,
                           ignore_patterns=ignore_patterns_in(element),
                           destination_directory=destination_directory)
    if element.tag == "pipeline":
        material_name = element.attrib.get('materialName', None)
        return PipelineMaterial(element.attrib['pipelineName'], element.attrib['stageName'], \
            material_name)
    raise RuntimeError("don't know of material matching " + ET.tostring(element, 'utf-8'))


class GitMaterial(CommonEqualityMixin):
    """
    GoCD Git Material.
    """
    def __init__(self, url, branch=None, material_name=None, polling=True, ignore_patterns=set(),\
     destination_directory=None):
        self.__url = url
        self.__branch = branch
        self.__material_name = material_name
        self.__polling = polling
        self.__ignore_patterns = ignore_patterns
        self.__destination_directory = destination_directory

    def append_to(self, element):
        """
        Append data to GoCD configuration XML
        """
        branch_part = ""
        if self.__branch is not None and self.__branch != 'master':
            branch_part = ' branch="%s"' % self.__branch

        material_name_part = ""
        if self.__material_name is not None:
            material_name_part = ' materialName="%s"' % self.__material_name

        polling_part = ''
        if not self.__polling:
            polling_part = ' autoUpdate="false"'

        destination_directory_part = ''
        if self.__destination_directory:
            destination_directory_part = ' dest="%s"' % self.__destination_directory

        new_element = ET.fromstring(('<git url="%s"' % self.__url) + branch_part + \
            material_name_part + polling_part + destination_directory_part + ' />')

        if self.__ignore_patterns:
            filter_element = ET.fromstring("<filter/>")
            new_element.append(filter_element)
            sorted_ignore_patterns = list(self.__ignore_patterns)
            sorted_ignore_patterns.sort()
            for ignore_pattern in sorted_ignore_patterns:
                filter_element.append(ET.fromstring('<ignore pattern="%s"/>' % ignore_pattern))

        element.append(new_element)


class PipelineMaterial(CommonEqualityMixin):
    """
    GoCD Pipeline Material.
    """
    def __init__(self, pipeline_name, stage_name, material_name=None):
        self.__pipeline_name = pipeline_name
        self.__stage_name = stage_name
        self.__material_name = material_name

    def append_to(self, element):
        """
        Append data to GoCD configuration XML
        """
        if self.__material_name is None:
            new_element = ET.fromstring('<pipeline pipelineName="%s" stageName="%s" />' % (\
                self.__pipeline_name, self.__stage_name))
        else:
            new_element = ET.fromstring(
                '<pipeline pipelineName="%s" stageName="%s" materialName="%s"/>' % (\
                    self.__pipeline_name, self.__stage_name, self.__material_name))

        element.append(new_element)
