from xml.etree import ElementTree as ET
from gomatic.gocd.artifacts import Artifact
from gomatic.gocd.generic import ThingWithResources, ThingWithEnvironmentVariables
from gomatic.gocd.materials import Materials, GitMaterial
from gomatic.gocd.tasks import Task
from gomatic.mixins import CommonEqualityMixin
from gomatic.xml_operations import PossiblyMissingElement, Ensurance, move_all_to_end


DEFAULT_LABEL_TEMPLATE = "0.${COUNT}"  # TODO confirm what default really is. I am pretty sure this is mistaken!


class Tab(CommonEqualityMixin):
    def __init__(self, name, path):
        self.__name = name
        self.__path = path

    def append_to(self, element):
        element.append(ET.fromstring('<tab name="%s" path="%s" />' % (self.__name, self.__path)))


class Job(CommonEqualityMixin):
    def __init__(self, element):
        self.__element = element
        self.__thing_with_resources = ThingWithResources(element)

    @property
    def name(self):
        return self.__element.attrib['name']

    @property
    def timeout(self):
        if not 'timeout' in self.__element.attrib:
            raise RuntimeError("Job (%s) does not have timeout" % self)
        return self.__element.attrib['timeout']

    @timeout.setter
    def timeout(self, timeout):
        self.__element.attrib['timeout'] = timeout

    def set_timeout(self, timeout):
        self.timeout = timeout
        return self

    @property
    def runs_on_all_agents(self):
        return self.__element.attrib.get('runOnAllAgents', 'false') == 'true'

    @runs_on_all_agents.setter
    def runs_on_all_agents(self, run_on_all_agents):
        self.__element.attrib['runOnAllAgents'] = 'true' if run_on_all_agents else 'false'

    def set_runs_on_all_agents(self, run_on_all_agents=True):
        self.runs_on_all_agents = run_on_all_agents
        return self

    @property
    def resources(self):
        return self.__thing_with_resources.resources

    def ensure_resource(self, resource):
        self.__thing_with_resources.ensure_resource(resource)
        return self

    @property
    def artifacts(self):
        artifact_elements = PossiblyMissingElement(self.__element).possibly_missing_child("artifacts").iterator
        return set([Artifact.get_artifact_for(e) for e in artifact_elements])

    def ensure_artifacts(self, artifacts):
        if artifacts:
            artifacts_ensurance = Ensurance(self.__element).ensure_child("artifacts")
            artifacts_to_add = artifacts.difference(self.artifacts)
            for artifact in artifacts_to_add:
                artifact.append_to(artifacts_ensurance)
        return self

    @property
    def tabs(self):
        return [Tab(e.attrib['name'], e.attrib['path']) for e in PossiblyMissingElement(self.__element).possibly_missing_child('tabs').findall('tab')]

    def ensure_tab(self, tab):
        tab_ensurance = Ensurance(self.__element).ensure_child("tabs")
        if self.tabs.count(tab) == 0:
            tab.append_to(tab_ensurance)
        return self

    @property
    def tasks(self):
        return [Task(e) for e in PossiblyMissingElement(self.__element).possibly_missing_child("tasks").iterator]

    def ensure_task(self, task):
        if self.tasks.count(task) == 0:
            return task.append_to(self.__element)
        else:
            return task

    @property
    def environment_variables(self):
        return self.__thing_with_environment_variables.environment_variables

    @property
    def encrypted_environment_variables(self):
        return self.__thing_with_environment_variables.encrypted_environment_variables

    def ensure_environment_variables(self, environment_variables):
        self.__thing_with_environment_variables.ensure_environment_variables(environment_variables)
        return self

    def ensure_encrypted_environment_variables(self, environment_variables):
        self.__thing_with_environment_variables.ensure_encrypted_environment_variables(environment_variables)
        return self

    @property
    def __thing_with_environment_variables(self):
        return ThingWithEnvironmentVariables(self.__element)

    def reorder_elements_to_please_go(self):
        # see https://github.com/SpringerSBM/gomatic/issues/6
        move_all_to_end(self.__element, "environment_variables")
        move_all_to_end(self.__element, "tasks")
        move_all_to_end(self.__element, "tabs")
        move_all_to_end(self.__element, "resources")
        move_all_to_end(self.__element, "artifacts")


class Stage(CommonEqualityMixin):
    def __init__(self, element):
        self.element = element

    @property
    def name(self):
        return self.element.attrib['name']

    @property
    def jobs(self):
        job_elements = PossiblyMissingElement(self.element).possibly_missing_child('jobs').findall('job')
        return [Job(job_element) for job_element in job_elements]

    def ensure_job(self, name):
        job_element = Ensurance(self.element).ensure_child("jobs").ensure_child_with_attribute("job", "name", name)
        return Job(job_element.element)

    @property
    def environment_variables(self):
        return self.__thing_with_environment_variables.environment_variables

    @property
    def encrypted_environment_variables(self):
        return self.__thing_with_environment_variables.encrypted_environment_variables

    def ensure_environment_variables(self, environment_variables):
        self.__thing_with_environment_variables.ensure_environment_variables(environment_variables)
        return self

    def ensure_encrypted_environment_variables(self, environment_variables):
        self.__thing_with_environment_variables.ensure_encrypted_environment_variables(environment_variables)
        return self

    @property
    def __thing_with_environment_variables(self):
        return ThingWithEnvironmentVariables(self.element)

    def set_clean_working_dir(self):
        self.element.attrib['cleanWorkingDir'] = "true"
        return self

    @property
    def clean_working_dir(self):
        return PossiblyMissingElement(self.element).has_attribute('cleanWorkingDir', "true")

    @property
    def has_manual_approval(self):
        return PossiblyMissingElement(self.element).possibly_missing_child("approval").has_attribute("type", "manual")

    @property
    def fetch_materials(self):
        return not PossiblyMissingElement(self.element).has_attribute("fetchMaterials", "false")

    @fetch_materials.setter
    def fetch_materials(self, value):
        if value:
            PossiblyMissingElement(self.element).remove_attribute("fetchMaterials")
        else:
            Ensurance(self.element).set("fetchMaterials", "false")

    def set_fetch_materials(self, value):
        self.fetch_materials = value
        return self

    def set_has_manual_approval(self):
        Ensurance(self.element).ensure_child_with_attribute("approval", "type", "manual")
        return self

    def reorder_elements_to_please_go(self):
        move_all_to_end(self.element, "environmentvariables")
        move_all_to_end(self.element, "jobs")

        for job in self.jobs:
            job.reorder_elements_to_please_go()


class Pipeline(CommonEqualityMixin):
    def __init__(self, element, parent):
        self.element = element
        self.parent = parent

    @property
    def name(self):
        return self.element.attrib['name']

    @property
    def is_template(self):
        return self.parent == 'templates'  # but for a pipeline, parent is the pipeline group

    def __eq__(self, other):
        return isinstance(other, self.__class__) and ET.tostring(self.element, 'utf-8') == ET.tostring(other.element, 'utf-8') and self.parent == other.parent

    def set_automatic_pipeline_locking(self):
        self.element.attrib['isLocked'] = 'true'
        return self

    @property
    def has_automatic_pipeline_locking(self):
        return 'isLocked' in self.element.attrib and self.element.attrib['isLocked'] == 'true'

    @property
    def label_template(self):
        if 'labeltemplate' in self.element.attrib:
            return self.element.attrib['labeltemplate']
        else:
            raise RuntimeError("Does not have a label template")

    @label_template.setter
    def label_template(self, label_template):
        self.element.attrib['labeltemplate'] = label_template

    def set_label_template(self, label_template):
        self.label_template = label_template
        return self

    def set_default_label_template(self):
        self.label_template = DEFAULT_LABEL_TEMPLATE
        return self

    @property
    def __template_name(self):
        return self.element.attrib.get('template', None)

    @__template_name.setter
    def __template_name(self, template_name):
        self.element.attrib['template'] = template_name

    def set_template_name(self, template_name):
        self.__template_name = template_name
        return self

    @property
    def materials(self):
        elements = PossiblyMissingElement(self.element).possibly_missing_child('materials').iterator
        return [Materials(element) for element in elements]

    def __add_material(self, material):
        material.append_to(Ensurance(self.element).ensure_child('materials'))

    def ensure_material(self, material):
        if self.materials.count(material) == 0:
            self.__add_material(material)
        return self

    @property
    def is_based_on_template(self):
        return self.__template_name is not None

    @property
    def template(self):
        return next(template for template in self.parent.templates if template.name == self.__template_name)

    @property
    def environment_variables(self):
        return self.__thing_with_environment_variables.environment_variables

    @property
    def encrypted_environment_variables(self):
        return self.__thing_with_environment_variables.encrypted_environment_variables

    @property
    def unencrypted_secure_environment_variables(self):
        return self.__thing_with_environment_variables.unencrypted_secure_environment_variables

    def ensure_environment_variables(self, environment_variables):
        self.__thing_with_environment_variables.ensure_environment_variables(environment_variables)
        return self

    def ensure_encrypted_environment_variables(self, environment_variables):
        self.__thing_with_environment_variables.ensure_encrypted_environment_variables(environment_variables)
        return self

    def ensure_unencrypted_secure_environment_variables(self, environment_variables):
        self.__thing_with_environment_variables.ensure_unencrypted_secure_environment_variables(environment_variables)
        return self

    @property
    def __thing_with_environment_variables(self):
        return ThingWithEnvironmentVariables(self.element)

    @property
    def parameters(self):
        param_elements = PossiblyMissingElement(self.element).possibly_missing_child("params").findall("param")
        result = {}
        for param_element in param_elements:
            result[param_element.attrib['name']] = param_element.text
        return result

    def ensure_parameters(self, parameters):
        parameters_ensurance = Ensurance(self.element).ensure_child("params")
        for key, value in parameters.iteritems():
            parameters_ensurance.ensure_child_with_attribute("param", "name", key).set_text(value)
        return self

    @property
    def stages(self):
        return [Stage(stage_element) for stage_element in self.element.findall('stage')]

    def ensure_stage(self, name):
        stage_element = Ensurance(self.element).ensure_child_with_attribute("stage", "name", name)
        return Stage(stage_element.element)

    def reorder_elements_to_please_go(self):
        materials = self.materials
        self.remove_materials()
        for material in self.__reordered_materials_to_reduce_thrash(materials):
            self.__add_material(material)

        move_all_to_end(self.element, "params")
        move_all_to_end(self.element, "timer")
        move_all_to_end(self.element, "environmentvariables")
        move_all_to_end(self.element, "materials")
        move_all_to_end(self.element, "stage")

        for stage in self.stages:
            stage.reorder_elements_to_please_go()

    @property
    def timer(self):
        if self.has_timer:
            return self.element.find('timer').text
        else:
            raise RuntimeError("%s has no timer" % self)

    @property
    def has_timer(self):
        return self.element.find('timer') is not None

    def set_timer(self, timer, only_on_changes=False):
        if only_on_changes:
            Ensurance(self.element).ensure_child_with_attribute('timer', 'onlyOnChanges', 'true').set_text(timer)
        else:
            Ensurance(self.element).ensure_child('timer').set_text(timer)
        return self

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children().remove_attribute('labeltemplate')

    @property
    def timer_triggers_only_on_changes(self):
        element = self.element.find('timer')
        return "true" == element.attrib.get('onlyOnChanges')

    def remove_materials(self):
        PossiblyMissingElement(self.element).remove_all_children('materials')

    @staticmethod
    def __reordered_materials_to_reduce_thrash(materials):
        def cmp_materials(m1, m2):
            if m1.is_git:
                if m2.is_git:
                    return cmp(m1.url, m2.url)
                else:
                    return -1
            else:
                if m2.is_git:
                    return 1
                else:
                    return cmp(str(m1), str(m2))

        return sorted(materials, cmp_materials)


class PipelineGroup(CommonEqualityMixin):
    def __init__(self, element, configurator):
        self.element = element
        self.__configurator = configurator

    @property
    def name(self):
        return self.element.attrib['group']

    @property
    def templates(self):
        return self.__configurator.templates

    @property
    def pipelines(self):
        return [Pipeline(e, self) for e in self.element.findall('pipeline')]

    def _matching_pipelines(self, name):
        return [p for p in self.pipelines if p.name == name]

    def has_pipeline(self, name):
        return len(self._matching_pipelines(name)) > 0

    def find_pipeline(self, name):
        if self.has_pipeline(name):
            return self._matching_pipelines(name)[0]
        else:
            raise RuntimeError('Cannot find pipeline with name "%s" in %s' % (name, self.pipelines))

    def ensure_pipeline(self, name):
        pipeline_element = Ensurance(self.element).ensure_child_with_attribute('pipeline', 'name', name).element
        return Pipeline(pipeline_element, self)

    def ensure_removal_of_pipeline(self, name):
        for pipeline in self._matching_pipelines(name):
            self.element.remove(pipeline.element)
        return self

    def ensure_replacement_of_pipeline(self, name):
        pipeline = self.ensure_pipeline(name)
        pipeline.make_empty()
        return pipeline

    def make_empty(self):
        PossiblyMissingElement(self.element).remove_all_children().remove_attribute('labeltemplate')

def then(s):
    return '\\\n\t.' + s
