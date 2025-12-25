"""
Document analysis core logic for Document Portal.
This module provides the Analyzer class for extracting structured metadata and summaries from
text extracted from contract documents. It is designed to be modular, fast, and production-grade.
"""
import sys
from typing import Dict, Any
from utils.model_loader import ModelLoader
from logger import GLOBAL_LOGGER as log
from exception.custom_exception import DocumentPortalException
from model.models import Metadata
from langchain_core.output_parsers import JsonOutputParser
from langchain.output_parsers import OutputFixingParser
from prompt.prompt_library import PROMPT_REGISTRY

class Analyzer:
    """
    Analyzes documents using a pre-trained model. Modular and production-grade.
    """
    def __init__(self) -> None:
        try:
            self.loader = ModelLoader()
            self.llm = self.loader.load_llm()
            self.parser = JsonOutputParser(pydantic_object=Metadata)
            self.fixing_parser = OutputFixingParser.from_llm(parser=self.parser, llm=self.llm)
            self.prompt = PROMPT_REGISTRY["document_analysis"]
            log.info("Analyzer initialized successfully")
        except Exception as e:
            log.error(f"Error initializing Analyzer: {e}")
            raise DocumentPortalException("Error in Analyzer initialization", sys)

    def analyze(self, document_text: str) -> Dict[str, Any]:
        """
        Analyze a document's text and extract structured metadata & summary.
        Args:
            document_text (str): The text of the document to analyze.
        Returns:
            Dict[str, Any]: Structured metadata and summary.
        """
        try:
            chain = self.prompt | self.llm | self.fixing_parser
            log.info("Meta-data analysis chain initialized")
            response = chain.invoke({
                "format_instructions": self.parser.get_format_instructions(),
                "document_text": document_text
            })
            log.info("Metadata extraction successful", keys=list(response.keys()))
            return response
        except Exception as e:
            log.error("Metadata analysis failed", error=str(e))
            raise DocumentPortalException("Metadata extraction failed", sys)
