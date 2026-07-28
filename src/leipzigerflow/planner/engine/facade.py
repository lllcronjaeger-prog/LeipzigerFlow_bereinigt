from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from leipzigerflow.planner.engine.models import PlanningStrategy
from leipzigerflow.planner.engine.service import DispatchSimulationService

@dataclass(slots=True)
class PlanningKpiSummary:
    assigned_orders:int; open_orders:int; utilized_vehicles:int; proposed_tours:int
    empty_run_minutes:int; waiting_minutes:int; average_score:float
    utilization_percent:float; simulation_seconds:float; suggestions:int

@dataclass(slots=True)
class ReplayStep:
    sequence:int; phase:str; message:str; details:str=""; planning_day:date|None=None

@dataclass(slots=True)
class PlanningReplay:
    steps:list[ReplayStep]=field(default_factory=list)
    @property
    def is_empty(self)->bool: return not self.steps

class PlanningEngine:
    """Public facade for UI, tests and future integrations."""
    def __init__(self, session):
        self.session=session; self.service=DispatchSimulationService(session)
    def simulate(self, planning_day:date): return self.service.simulate(planning_day)
    def simulate_horizon(self,start_day:date,horizon_days:int=3,*,strategy:PlanningStrategy=PlanningStrategy.MAX_UTILIZATION):
        return self.service.simulate_horizon(start_day,horizon_days=horizon_days,strategy=strategy)
    def apply(self,result:Any,planning_day:date)->tuple[int,int]: return self.service.apply(result,planning_day)
    def apply_horizon(self,result:Any)->tuple[int,int]: return self.service.apply_horizon(result)
    @staticmethod
    def evaluate(result:Any)->PlanningKpiSummary:
        return PlanningKpiSummary(int(getattr(result,'assigned_count',0)),int(getattr(result,'open_count',0)),int(getattr(result,'utilized_vehicle_count',0)),int(getattr(result,'proposed_tour_count',0)),int(getattr(result,'total_transfer_minutes',0)),int(getattr(result,'total_waiting_minutes',0)),float(getattr(result,'average_score',0.0)),float(getattr(result,'utilization_percent',0.0)),float(getattr(result,'simulation_seconds',0.0)),int(getattr(result,'suggestion_count',0)))
    @staticmethod
    def replay(result:Any)->PlanningReplay:
        replay=PlanningReplay(); daily=getattr(result,'daily_results',None)
        if isinstance(daily,dict):
            seq=1
            for day,day_result in sorted(daily.items()):
                for entry in getattr(day_result,'planning_trace',[]) or []:
                    phase=getattr(getattr(entry,'phase',None),'value',str(getattr(entry,'phase','')))
                    replay.steps.append(ReplayStep(seq,phase,str(getattr(entry,'message','')),str(getattr(entry,'details','')),day)); seq+=1
            return replay
        for idx,entry in enumerate(getattr(result,'planning_trace',[]) or [],1):
            phase=getattr(getattr(entry,'phase',None),'value',str(getattr(entry,'phase','')))
            replay.steps.append(ReplayStep(idx,phase,str(getattr(entry,'message','')),str(getattr(entry,'details',''))))
        return replay
