import xml.etree.ElementTree as ET
from pathlib import Path
import glob
from html.parser import HTMLParser
import argparse


class HTMLFilter(HTMLParser):
    text = ""

    def handle_data(self, data):
        self.text += data
def html_to_string(html):
    """
    See https://stackoverflow.com/a/55825140
    :param html:
    :return:
    """
    f = HTMLFilter()
    f.feed(html)
    return f.text


class CanvasAnswer:
    """
    Represents a correct or incorrect answer to a canvas question with support for parsing, identification
    and marking as correct or incorrect (default is incorrect)
    """
    def __init__(self, ns, element):
        self.ns = ns
        self.element = element
        self.correct = False
        self.ident = None
        self.text = None

    def set_correct(self, correct):
        self.correct = correct

    def get_ident(self):
        return self.element.get('ident')

    def get_text(self):
        return html_to_string(self.element.find(f'.//{self.ns}mattext').text)


class CanvasQuestion:
    """
    Represents a canvas question.  Methods for building questions from a question element in a
    canvas object bank.
    Supports several canvas question types.
    Support for matching_question is not complete, tailored for the conversion to coursera which doesn't
    support this type.  Search output files for converted_matching_question to find the questions which will
    need attention/review/edit before import on coursera.
    """

    def __init__(self, ns, element):
        self.ns = ns
        self.element = element
        self.type = None
        self.text = None
        self.answers = []
        self.variation = None
        self.response_lid_elem = None
        self.resprocessing_parent = None

    def set_variation(self, variation):
        """
        Coursera questions support variations, where only one variation is shown in a given quiz taking session.
        By default, assume a question has no variations, but allow this to be set in the case it does (see
        matching_question type).
        :param variation:
        :return:
        """
        self.variation = variation

    def set_text(self, text):
        """
        Override the text taken from the element in the case we want to do something different for this question.
        See matching_question type which overrides to add custom text.
        :param text:
        :return:
        """
        self.text = text

    def set_type(self, type):
        """
        Override the question type from the value obtained from xml.  Necessary when building multiple questions
        from a single coursera question (see matching_question type).
        :param type:
        :return:
        """
        self.type = type

    def set_response_lid_elem(self, elem):
        """
        Override the response_lid element, describing this question, from the default.  This is used for
        matching_question types to allow splitting a single matching question into multiple questions supported
        by Coursera.
        :param elem: the element to use as the response_lid element, rather than finding from self.elem
        :return:
        """
        self.response_lid_elem = elem

    def set_resprocessing_parent(self, elem):
        self.resprocessing_parent = elem

    @staticmethod
    def get_question_type(namespace, question_elem):
        type = None
        for fieldlabel_parent in question_elem.findall(f'.//{namespace}fieldlabel/..'):
            if fieldlabel_parent.find(f'.//{namespace}fieldlabel').text == 'question_type':
                type = fieldlabel_parent.find(f'.//{namespace}fieldentry').text
                break
        return type

    @staticmethod
    def get_question_text(namespace, question_elem):
        return html_to_string(question_elem.find(f'.//{namespace}mattext').text)

    @staticmethod
    def canvas_question_builder(namespace, question_elem):
        """
        Builds a list of CanvasQuestion values from a question element in xml.
        Typically this will just be one question in the list, however the coursera conversion for matching_question
        will return multiple questions
        :param namespace: the namespace of the xml file
        :param question_elem: The element describing the question to convert
        :return: a list of CanvasQuestion objects representing the question
        """
        questions = []
        type = CanvasQuestion.get_question_type(namespace, question_elem)
        if type == 'matching_question':
            variation = 1
            for response in question_elem.findall(f'.//{namespace}response_lid'):
                question = CanvasQuestion(namespace, response)
                question.set_variation(variation)
                variation = variation + 1
                question.set_type('matching_question')
                question.set_text(CanvasQuestion.get_question_text(namespace, question_elem) +
                                  " (converted_matching_question) select the best definition for term " +
                                  f"{CanvasQuestion.get_question_text(namespace, response)}")
                question.set_response_lid_elem(response)
                question.set_resprocessing_parent(question_elem.find(
                                    f'.//{namespace}varequal[@respident=\'{response.get("ident")}\']../..'))
                questions.append(question)
        else:
            question = CanvasQuestion(namespace, question_elem)
            if question.supported():
                questions.append(question)
            else:
                print(f"Question type {question.get_type()} not yet supported")
        return questions

    def get_type(self):
        """
        :return: the question type of this question
        """
        if self.type is None:
            self.type = CanvasQuestion.get_question_type(self.ns, self.element)
        return self.type

    def get_text(self):
        """
        :return: The text of this question as a string (without possible answers)
        """
        if self.text is None:
            self.text = CanvasQuestion.get_question_text(self.ns, self.element)
        return self.text

    def supported(self):
        """
        :return: True if this canvas question type is supported by the parser
        Note that matching_question support is minimal, but better than nothing (hopefully)
        """
        return self.get_type() == 'true_false_question' or \
               self.get_type() == 'multiple_answers_question' or \
               self.get_type() == 'multiple_choice_question' or \
               self.get_type() == 'matching_question'

    def get_response_lid(self):
        """
        :return: the reference to the response_lid element, which may be overridden in the case this question
        is split into multiple (see the matching_question type).
        """
        if self.response_lid_elem is None:
            self.response_lid_elem = self.element.find(f'.//{self.ns}response_lid')
        return self.response_lid_elem

    def get_resprocessing_parent(self):
        if self.resprocessing_parent == None:
            return self.element
        return self.resprocessing_parent

    def get_answers(self):
        if len(self.answers) == 0:
            for response in self.get_response_lid().findall(f'.//{self.ns}response_label'):
                self.answers.append(CanvasAnswer(self.ns, response))
            for response_parent in self.get_resprocessing_parent().findall(f'.//{self.ns}varequal/..'):
                tag = response_parent.tag.replace(self.ns, "")
                if tag != 'not':
                    for response in response_parent.findall(f'.{self.ns}varequal'):
                        for answer in self.answers:
                            if answer.get_ident() == response.text:
                                answer.set_correct(True)
                                break

        return self.answers

    def get_coursera_description(self):
        """
        Map the Canvas question type to the description used for import into Coursera question import templates.
        These could be customized, this is just what I've found works well for my questions
        :return:
        """
        rtn_text = ""
        if self.get_type() == 'true_false_question':
            # Don't shuffle, so true is always first.
            rtn_text = "multiple choice, no shuffle"
        elif self.get_type() == 'multiple_answers_question':
            # Shuffle multiple answers and use checkbox type to allow multiple
            rtn_text = "checkbox, partial credit, shuffle"
        elif self.get_type() == 'multiple_choice_question' or self.get_type() == 'matching_question':
            # Shuffle multiple choice options.  If variations are defined, use them.
            rtn_text = "multiple choice, shuffle"

        if self.variation:
            rtn_text = f"{rtn_text}, variation {self.variation}"

        return rtn_text


    def get_coursera_answers(self):
        """
        :return: a text representation of answers to this question in the format expected for the Coursera
         import template, with incrementing Alpha letters for each answer option and a star in front of the
         correct answer(s).
        """
        rtn_text = ""
        alpha = 'A'
        for answer in self.get_answers():
            if answer.correct:
                rtn_text += f"*{alpha}: {answer.get_text()}\n"
            else:
                rtn_text += f"{alpha}: {answer.get_text()}\n"
                rtn_text += f"Feedback: \n"
            alpha = chr(ord(alpha) + 1)
        return rtn_text

    def get_coursera_text(self, question_num):
        """
        :param question_num: The number to use for this question.  Coursera expects these to be linearly increasing
        in the import document for a given set of question banks and a given question import document
        :return: A string representing the question in Coursera import format, including the question number,
        a description, the question text, and all answers possible and actual
        """
        if self.supported():
            return (f"Question {question_num} - {self.get_coursera_description()} \n"
                    f"{self.get_text()}\n"
                    f"{self.get_coursera_answers()}")
        else:
            print(f'Attempted to call get_coursera_text on unsupported type {self.get_type()}')


class CanvasObjectBank:
    """
    A class describing a question bank associated with one or more assessments in Coursera
    """
    def __init__(self, ns, element):
        """
        :param ns: The xml namespace to use
        :param element: The element describing this object bank
        """
        self.ns = ns
        self.element = element
        self.questions = []
        self.num_questions_coursera_count = None

    def get_questions(self):
        """
        :return: a list of CanvasQustion objects associated with this Question bank.
        """

        if len(self.questions) == 0:
            for item in self.element:
                if item.get('title') == 'Question':
                    self.questions.extend(CanvasQuestion.canvas_question_builder(self.ns, item))
        return self.questions

    def dump_coursera(self, question_num):
        """
        :param question_num: The starting question number to use for the bank
        :return: A text representation of all quesitons in the question bank, suitable for placing in a Coursera
        import document.
        """
        text = ""
        prev_variation = None
        self.num_questions_coursera_count = 0
        first_question = True
        for question in self.get_questions():

            if question.variation is None or \
                    prev_variation is not None and question.variation < prev_variation or \
                    prev_variation is None and question.variation is not None:
                self.num_questions_coursera_count = self.num_questions_coursera_count + 1
                if not first_question:
                    #Never increment the question number for the initial question
                    question_num = question_num + 1
            prev_variation = question.variation
            text += question.get_coursera_text(question_num) + "\n\n\n"
            first_question = False
        return text

    def num_questions_coursera(self):
        """
        :return: The number of unique questions from a coursera question count import document perspecive.
        This may not equal the total number of CanvasQuestion objects since some question types, like matching_quesiton,
        result in more questions (variations) which are not included in the coursera questions count.
        """
        if self.num_questions_coursera_count is None:
            self.dump_coursera(1)
        return self.num_questions_coursera_count

    def get_title(self):
        title = "Unknown"
        for bank_title_parent in self.element.findall(f'.//{self.ns}fieldlabel/..'):
            if bank_title_parent.find(f'.//{self.ns}fieldlabel').text == 'bank_title':
                title = bank_title_parent.find(f'{self.ns}fieldentry').text
        return title



class CanvasAssessment:
    """
    A Canvas assessment (quiz/test) including one or more question banks (object banks)
    """
    def __init__(self, ns, element):
        """
        :param ns: The XML namespace
        :param element: The element corresponding to this assessment
        """
        self.ns = ns
        self.element = element
        self.objbanks = []

    def set_objbanks(self, objbank_dict):
        """
        Setup the object banks for the assessment based on the references to object banks in the assesment
        and the dictionary populated with all assessments.
        :param objbank_dict: A dictionary containing all object banks for the course, with ident as key.
        """
        for sourcebank in self.element.findall(f'.//{self.ns}sourcebank_ref'):
            self.objbanks.append(objbank_dict[sourcebank.text])

    def dump_coursera(self):
        """
        :return: Text describing the Assesment in coursera format, containing all associated question banks
        and their associated questions.
        """
        text = ""
        question_number = 1
        for objbank in self.objbanks:
            text = text + objbank.dump_coursera(question_number)
            question_number += objbank.num_questions_coursera()
        return text


class CanvasXmlReader:
    """
    Read an XML file exported from a canvas course export
    """
    def __init__(self, file):
        """
        :param file: An XML (qti) file found in the canvas course export
        """
        self.file = file
        self.ns = None

    def default_ns(self):
        """
        :return: The namespace to use for XML lookups.  This is needed for python versions earlier than 3.8 since
        the ET class didnt' support wildcard namespace lookups.
        """
        if self.ns is None:
            # see https://medium.datadriveninvestor.com/getting-started-using-pythons-elementtree-to-navigate-xml-files-dc9bc720eaa6
            namespaces = {node[0]: node[1] for _, node in ET.iterparse(self.file, events=['start-ns'])}
            # Iterates through the newly created namespace list registering each one.
            for key, value in namespaces.items():
                ET.register_namespace(key, value)
            self.ns = "{" + namespaces[""] + "}"
        return self.ns

    def parse_canvas_qti(self, assessment_dict, objectbank_dict):
        """
        Fills dictionaries with the contents in this .qti canvas export XML file, using "ident" as key
        to allow later lookups between assessments and object banks.
        :param assessment_dict: Dictionary to fill with assessment information in this qti file, if any
        :param objectbank_dict: Dictionary to fill with objectbank information in this qti file, if any.
        :return:
        """
        tree = ET.parse(self.file)
        root = tree.getroot()
        assessment = root.find(f'{self.default_ns()}assessment')
        if assessment:
            assessment_dict[assessment.get('ident')] = CanvasAssessment(self.default_ns(), assessment)
        objectbank = root.find(f'{self.default_ns()}objectbank')
        if objectbank:
            objectbank_dict[objectbank.get('ident')] = CanvasObjectBank(self.default_ns(), objectbank)


def canvas_export_to_coursera(export_path):
    """
    Using a canvas course export, iterate through all assessments and dump out import files ready for
    Coursera import.  Import files will be created: One per assessment and one per question bank, and named
    based on the assessment or question bank
    :param export_path: The path to the unzipped export directory of a canvas course
    """
    assessments_path = export_path / "non_cc_assessments"
    assessment = {}
    objectbank = {}
    for file in assessments_path.glob("*.xml.qti"):
        try:
            reader = CanvasXmlReader(file)
            reader.parse_canvas_qti(assessment, objectbank)
        except Exception as e:
            print(f"Failed to process {file} with error {e}")
    for key in assessment:
        assessment[key].set_objbanks(objectbank)
        print(f"Creating Assessment coursera output for {assessment[key].element.get('title')}")
        with open(Path(export_path /
                        (assessment[key].element.get('title').replace(" ", "_").replace(":", "_") +".txt" )), "w") \
                as of:
            of.writelines(assessment[key].dump_coursera())
    for key in objectbank:
        print(f"Creating Object bank coursera output for {objectbank[key].get_title()}")
        with open(Path(export_path /
                        (objectbank[key].get_title().replace(" ", "_").replace(":", "_") +".txt" )), "w") \
                as of:
            of.writelines(objectbank[key].dump_coursera(1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create files suitable for import of questions into Coursera'
                                                 ' given a Canvas course export')
    parser.add_argument('--export_path', help='The full path to an exported canvas course shell'
                                            '(renamed from .imscc to .zip and extracted to this directory)')
    args = parser.parse_args()
    if args.export_path is None:
        print("You must specify --export_path")
        parser.print_help()
        exit(1)

    canvas_export_to_coursera(Path(args.export_path))
