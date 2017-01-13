from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from simplegomatic.gocd.artifacts import fetch_artifact_src_from
from simplegomatic.mixins import CommonEqualityMixin
from simplegomatic.xml_operations import Ensurance


def Task(element):
    """
    Task instance initializer
    """
    runif = runif_from(element)
    if element.tag == "exec":
        command_and_args = [element.attrib["command"]] + [e.text for e in element.findall('arg')]
        # TODO not ideal to return "None" for working_dir
        working_dir = element.attrib.get("workingdir", None)
        return ExecTask(command_and_args, working_dir, runif)
    if element.tag == "fetchartifact":
        dest = element.attrib.get('dest', None)
        return FetchArtifactTask(
            element.attrib['pipeline'], element.attrib['stage'],
            element.attrib['job'], fetch_artifact_src_from(element),
            dest, runif)
    if element.tag == "rake":
        return RakeTask(element.attrib['target'])
    raise RuntimeError("Don't know task type %s" % element.tag)


class AbstractTask(CommonEqualityMixin):
    """
    Base Task class
    """
    def __init__(self, runif):
        self._runif = runif
        valid_values = ['passed', 'failed', 'any']
        if runif not in valid_values:
            raise RuntimeError('Cannot create task with runif="%s" - it must be one of %s' % (runif, valid_values))

    @property
    def runif(self):
        return self._runif


class FetchArtifactTask(AbstractTask):
    """
    GOCG Fetch Artifact task
    """
    def __init__(self, pipeline, stage, job, src, dest=None, runif="passed"):
        super(self.__class__, self).__init__(runif)
        self.__pipeline = pipeline
        self.__stage = stage
        self.__job = job
        self.__src = src
        self.__dest = dest

    type = 'fetchartifact'

    def append_to(self, element):
        """
        Append data to GoCD configuration XML
        """
        src_type, src_value = self.__src.as_xml_type_and_value
        if self.__dest is None:
            new_element = ET.fromstring(
                '<fetchartifact pipeline="%s" stage="%s" job="%s" %s="%s" />' % (self.__pipeline, \
                self.__stage, self.__job, src_type, src_value))
        else:
            new_element = ET.fromstring(
                '<fetchartifact pipeline="%s" stage="%s" job="%s" %s="%s" dest="%s"/>' % (
                    self.__pipeline, self.__stage, self.__job, src_type, src_value, self.__dest))
        new_element.append(ET.fromstring('<runif status="%s" />' % self.runif))

        Ensurance(element).ensure_child("tasks").append(new_element)
        return Task(new_element)


class ExecTask(AbstractTask):
    """
    GOCG Exec task
    """
    def __init__(self, command_and_args, working_dir=None, runif="passed"):
        super(self.__class__, self).__init__(runif)
        self.__command_and_args = command_and_args
        self.__working_dir = working_dir

    type = 'exec'

    def append_to(self, element):
        """
        Append data to GoCD configuration XML
        """
        if self.__working_dir is None:
            new_element = ET.fromstring('<exec command="%s"></exec>' % self.__command_and_args[0])
        else:
            new_element = ET.fromstring('<exec command="%s" workingdir="%s"></exec>' % \
                (self.__command_and_args[0], self.__working_dir))

        for arg in self.__command_and_args[1:]:
            new_element.append(ET.fromstring('<arg>%s</arg>' % escape(arg)))

        new_element.append(ET.fromstring('<runif status="%s" />' % self.runif))

        Ensurance(element).ensure_child("tasks").append(new_element)
        return Task(new_element)


class RakeTask(AbstractTask):
    """
    GOCG Rake task
    """
    def __init__(self, target, runif="passed"):
        super(self.__class__, self).__init__(runif)
        self.__target = target

    type = 'rake'

    def append_to(self, element):
        """
        Append data to GoCD configuration XML
        """
        new_element = ET.fromstring('<rake target="%s"></rake>' % self.__target)
        Ensurance(element).ensure_child("tasks").append(new_element)
        return Task(new_element)


def runif_from(element):
    """
    Checks is runif status is valid
    """
    runifs = [e.attrib['status'] for e in element.findall("runif")]
    if len(runifs) == 0:
        return 'passed'
    if len(runifs) == 1:
        return runifs[0]
    if len(runifs) == 2 and 'passed' in runifs and 'failed' in runifs:
        return 'any'
    raise RuntimeError("Don't know what multiple runif values (%s) means" % runifs)