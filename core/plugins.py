from core.interfaces import BaseSearchEngine, BaseJobParser, BaseApplyEngine
from engines.search.fallback import FallbackSearch

# Search Engines
from engines.greenhouse.search import GreenhouseSearch
from engines.lever.search import LeverSearch
from engines.linkedin.search import LinkedInSearch
from engines.ashby.search import AshbySearch
from engines.workable.search import WorkableSearch
from engines.naukri.search import NaukriSearch
from engines.instahyre.search import InstahyreSearch
from engines.wellfound.search import WellfoundSearch
from engines.hirist.search import HiristSearch
from engines.cutshort.search import CutshortSearch
from engines.indeed.search import IndeedSearch
from engines.foundit.search import FounditSearch
from engines.glassdoor.search import GlassdoorSearch

# Parser Engines
from engines.parser.job_parser import DefaultJobParser
from engines.greenhouse.parser import GreenhouseJobParser
from engines.lever.parser import LeverJobParser
from engines.linkedin.parser import LinkedInJobParser
from engines.ashby.parser import AshbyJobParser
from engines.workable.parser import WorkableJobParser
from engines.naukri.parser import NaukriJobParser
from engines.instahyre.parser import InstahyreJobParser
from engines.wellfound.parser import WellfoundJobParser
from engines.hirist.parser import HiristJobParser
from engines.cutshort.parser import CutshortJobParser
from engines.indeed.parser import IndeedJobParser
from engines.foundit.parser import FounditJobParser
from engines.glassdoor.parser import GlassdoorJobParser

# Apply Engines
from engines.apply.universal import UniversalApply
from engines.greenhouse.apply import GreenhouseApply
from engines.lever.apply import LeverApply
from engines.linkedin.apply import LinkedInApply
from engines.ashby.apply import AshbyApply
from engines.workable.apply import WorkableApply
from engines.naukri.apply import NaukriApply
from engines.instahyre.apply import InstahyreApply
from engines.wellfound.apply import WellfoundApply
from engines.hirist.apply import HiristApply
from engines.cutshort.apply import CutshortApply
from engines.indeed.apply import IndeedApply
from engines.foundit.apply import FounditApply
from engines.glassdoor.apply import GlassdoorApply

# Plugin Registry
SEARCH_ENGINES = {
    "fallback": FallbackSearch,
    "greenhouse": GreenhouseSearch,
    "lever": LeverSearch,
    "linkedin": LinkedInSearch,
    "ashby": AshbySearch,
    "workable": WorkableSearch,
    "naukri": NaukriSearch,
    "instahyre": InstahyreSearch,
    "wellfound": WellfoundSearch,
    "hirist": HiristSearch,
    "cutshort": CutshortSearch,
    "indeed": IndeedSearch,
    "foundit": FounditSearch,
    "glassdoor": GlassdoorSearch
}

PARSER_ENGINES = {
    "default": DefaultJobParser,
    "greenhouse": GreenhouseJobParser,
    "lever": LeverJobParser,
    "linkedin": LinkedInJobParser,
    "ashby": AshbyJobParser,
    "workable": WorkableJobParser,
    "naukri": NaukriJobParser,
    "instahyre": InstahyreJobParser,
    "wellfound": WellfoundJobParser,
    "hirist": HiristJobParser,
    "cutshort": CutshortJobParser,
    "indeed": IndeedJobParser,
    "foundit": FounditJobParser,
    "glassdoor": GlassdoorJobParser
}

APPLY_ENGINES = {
    "universal": UniversalApply,
    "greenhouse": GreenhouseApply,
    "lever": LeverApply,
    "linkedin": LinkedInApply,
    "ashby": AshbyApply,
    "workable": WorkableApply,
    "naukri": NaukriApply,
    "instahyre": InstahyreApply,
    "wellfound": WellfoundApply,
    "hirist": HiristApply,
    "cutshort": CutshortApply,
    "indeed": IndeedApply,
    "foundit": FounditApply,
    "glassdoor": GlassdoorApply
}
