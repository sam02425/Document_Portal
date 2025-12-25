"""
Document comparison core logic for Document Portal.
This module provides the Comparator class for comparing two contract documents and returning
structured, page-wise differences. It is modular and ready for production use.
"""
import sys
import pandas as pd
from typing import Any, List
from utils.model_loader import ModelLoader
from logger import GLOBAL_LOGGER as log
from exception.custom_exception import DocumentPortalException
from prompt.prompt_library import PROMPT_REGISTRY
from model.models import SummaryResponse, PromptType
from langchain_core.output_parsers import JsonOutputParser
from langchain.output_parsers import OutputFixingParser

class Comparator:
    """
    Compares two documents using a pre-trained LLM and returns structured comparison data.
    Modular and production-grade.
    """
    def __init__(self) -> None:
        try:
            self.loader = ModelLoader()
            self.llm = self.loader.load_llm()
            self.parser = JsonOutputParser(pydantic_object=SummaryResponse)
            self.fixing_parser = OutputFixingParser.from_llm(parser=self.parser, llm=self.llm)
            self.prompt = PROMPT_REGISTRY[PromptType.DOCUMENT_COMPARISON.value]
            self.chain = self.prompt | self.llm | self.parser
            log.info("Comparator initialized", model=str(self.llm))
        except Exception as e:
            log.error(f"Error initializing Comparator: {e}")
            raise DocumentPortalException("Error in Comparator initialization", sys)

    def compare(self, combined_docs: str) -> pd.DataFrame:
        """
        Compare two documents and return structured comparison data as a DataFrame.
        Args:
            combined_docs (str): Combined text of both documents for comparison.
        Returns:
            pd.DataFrame: Comparison results.
        """
        try:
            inputs = {
                "combined_docs": combined_docs,
                "format_instruction": self.parser.get_format_instructions()
            }
            log.info("Invoking document comparison LLM chain")
            response = self.chain.invoke(inputs)
            log.info("Chain invoked successfully", response_preview=str(response)[:200])
            return self._format_response(response)
        except Exception as e:
            log.error("Error in compare", error=str(e))
            raise DocumentPortalException("Error comparing documents", sys)

    def _format_response(self, response_parsed: List[dict]) -> pd.DataFrame:
        try:
            df = pd.DataFrame(response_parsed)
            return df
        except Exception as e:
            log.error("Error formatting response into DataFrame", error=str(e))
            raise DocumentPortalException("Error formatting response", sys)
