from core.interfaces import BaseSearchEngine, BaseJobParser, BaseApplyEngine
from engines.search.fallback import FallbackSearch

from engines.greenhouse.search import GreenhouseSearch
from engines.lever.search import LeverSearch
from engines.linkedin.search import LinkedInSearch
from engines.ashby.search import AshbySearch
from engines.workable.search import WorkableSearch

from engines.parser.job_parser import DefaultJobParser
from engines.greenhouse.parser import GreenhouseJobParser
from engines.lever.parser import LeverJobParser
from engines.linkedin.parser import LinkedInJobParser
from engines.ashby.parser import AshbyJobParser
from engines.workable.parser import WorkableJobParser

from engines.apply.universal import UniversalApply
from engines.greenhouse.apply import GreenhouseApply
from engines.lever.apply import LeverApply
from engines.linkedin.apply import LinkedInApply
from engines.ashby.apply import AshbyApply
from engines.workable.apply import WorkableApply

# Plugin Registry
SEARCH_ENGINES = {
    "fallback": FallbackSearch,
    "greenhouse": GreenhouseSearch,
    "lever": LeverSearch,
    "linkedin": LinkedInSearch,
    "ashby": AshbySearch,
    "workable": WorkableSearch
}

PARSER_ENGINES = {
    "default": DefaultJobParser,
    "greenhouse": GreenhouseJobParser,
    "lever": LeverJobParser,
    "linkedin": LinkedInJobParser,
    "ashby": AshbyJobParser,
    "workable": WorkableJobParser
}

APPLY_ENGINES = {
    "universal": UniversalApply,
    "greenhouse": GreenhouseApply,
    "lever": LeverApply,
    "linkedin": LinkedInApply,
    "ashby": AshbyApply,
    "workable": WorkableApply
}
