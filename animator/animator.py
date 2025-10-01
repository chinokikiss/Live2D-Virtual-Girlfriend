import time
import random
from config import Global
from utils.calculation import *
import numpy as np

class Timer:
    def __init__(self, interval):
        self.t = time.time()
        self.count = 0
        self.interval = interval
    
    def time(self):
        t = time.time()
        if t - self.t - self.count*self.interval > self.interval:
            self.count += 1
            self.t = t - self.count*self.interval
        
        return round(t - self.t, 5)

class Live2dAnimator:
    def __init__(self, model):
        self.model = model
        self.priority_list = []
        self.params = {}
        self.blacklist1 = []
        self.blacklist2 = []
        for i in range(self.model.GetParameterCount()):
            param = self.model.GetParameter(i)
            self.params[param.id] = param.value
        print(self.params)
        
    def add(self, priority, animator):
        for i in range(len(self.priority_list)):
            if self.priority_list[i][0] >= priority:
                break
        else:
            i = len(self.priority_list)
        
        self.priority_list.insert(i, (priority, animator))
    
    def update(self):
        results = []
        for i in range(len(self.priority_list)-1, -1, -1):
            animator = self.priority_list[i][1]
            result = animator.update()
            if result is None:
                self.priority_list.pop(i)
            else:
                results.extend(result)
        
        for param, value, weight in results:
            if param in self.params:
                self.params[param] = self.params[param] * (1 - weight) + value * weight
                self.model.SetParameterValue(param, value, weight)

class LipSyncHandler:
    def __init__(self, max_rms_scale=Global.character["max_rms_scale"]):
        self.model = Global.model
        self.smoothing_factor = 0.3
        self.last_mouth_value = 0.0
        self.silence_threshold = 0 # 静音阈值
        self.max_rms_scale = max_rms_scale
        self.mouth_scale = 1.0 # 整体嘴巴开合缩放
        
    def update_mouth_sync(self, audio_chunk):
        """更新口型同步"""
        rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))
        
        if rms < self.silence_threshold:
            mouth_value = 0.0
        else:
            normalized_rms = (rms - self.silence_threshold) / self.max_rms_scale
            mouth_value = min(normalized_rms ** 2.0, 1.0) * self.mouth_scale
        
        smoothed_value = (self.smoothing_factor * mouth_value + 
                        (1 - self.smoothing_factor) * self.last_mouth_value)
        
        self.model.SetParameterValue("ParamMouthOpenY", smoothed_value)
        self.last_mouth_value = smoothed_value

class BlinkAnimator:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.flag = None
        self.k = None
        self.reset()
    
    def reset(self):
        self.k = min(1, random.uniform(0.8, 1.5))
        if random.random() > 0.3:
            self.flag = 0
        else:
            self.flag = 1
        self.flag1 = 0
        self.interval = 0.2
        self.timer = Timer(self.interval)
        self.wait = False

    def update(self):
        t = self.timer.time() / self.interval

        if self.wait:
            if t > self.wait_time and 'BlinkAnimator' not in Global.live2d_animator.blacklist1 and 'BlinkAnimator' not in Global.live2d_animator.blacklist2:
                self.reset()
        else:
            if self.flag == 0:
                if t <= 1:
                    eased_t = sine(t)
                    if self.flag1 == 0:
                        self.flag1 += 1
                        self.s1 = self.params['ParamEyeLOpen']
                        self.s2 = self.params['ParamEyeROpen']
                    return [
                        ('ParamEyeLOpen', round(linearScale1(eased_t, 0, 1, self.s1, 0), 2), 1),
                        ('ParamEyeROpen', round(linearScale1(eased_t, 0, 1, self.s2, 0), 2), 1),
                    ]
                elif 1 < t <= 2:
                    t -= 1
                    eased_t = sine(t)
                    if self.flag1 == 1:
                        self.flag1 += 1
                        self.s1 = self.params['ParamEyeLOpen']
                        self.s2 = self.params['ParamEyeROpen']
                    return [
                        ('ParamEyeLOpen', round(linearScale1(eased_t, 0, 1, self.s1, self.k), 2), 1),
                        ('ParamEyeROpen', round(linearScale1(eased_t, 0, 1, self.s2, self.k), 2), 1),
                    ]
                else:
                    self.wait = True
                    if random.random() > 0.3:
                        self.wait_time = random.randint(20, 40)
                    else:
                        self.wait_time = 0
                    self.timer = Timer(self.interval)

                    return [
                        ('ParamEyeLOpen', self.k, 1),
                        ('ParamEyeROpen', self.k, 1),
                    ]

            elif self.flag == 1:
                if t <= 1:
                    eased_t = sine(t)
                    if self.flag1 == 0:
                        self.flag1 += 1
                        self.s1 = self.params['ParamEyeLOpen']
                        self.s2 = self.params['ParamEyeROpen']
                    return [
                        ('ParamEyeLOpen', round(linearScale1(eased_t, 0, 1, self.s1, self.k), 2), 1),
                        ('ParamEyeROpen', round(linearScale1(eased_t, 0, 1, self.s2, self.k), 2), 1),
                    ]
                else:
                    self.wait = True
                    if random.random() > 0.3:
                        self.wait_time = random.randint(20, 40)
                    else:
                        self.wait_time = 0
                    self.timer = Timer(self.interval)

                    return [
                        ('ParamEyeLOpen', self.k, 1),
                        ('ParamEyeROpen', self.k, 1),
                    ]

        return []

class EyeBallAnimator:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.reset()
    
    def reset(self):
        self.wait = False
        self.interval = 0.2
        self.timer = Timer(self.interval)
        self.k1 = random.uniform(-1, 1)
        self.k2 = random.uniform(-0.5, 0.5)
        self.flag1 = 0
        self.easing_functions = [
            cubic,
            quart,
            sine
        ]
        self.current_easing = random.choice(self.easing_functions)
    
    def move_to_center(self):
        self.reset()
        self.k1 = 0
        self.k2 = 0
    
    def update(self):
        current_time = self.timer.time() 
        t = current_time / self.interval
        if self.wait:
            if current_time > self.fixation_time and Global.blink_animator.wait and 'EyeBallAnimator' not in Global.live2d_animator.blacklist1 and 'EyeBallAnimator' not in Global.live2d_animator.blacklist2:
                self.reset()
        else:
            if t <= 1:
                eased_t = self.current_easing(t)
                if self.flag1 == 0:
                    self.flag1 += 1
                    self.s1 = self.params['ParamEyeBallX']
                    self.s2 = self.params['ParamEyeBallY']
                return [
                    ('ParamEyeBallX', round(linearScale1(eased_t, 0, 1, self.s1, self.k1), 2), 1),
                    ('ParamEyeBallY', round(linearScale1(eased_t, 0, 1, self.s2, self.k2), 2), 1),
                ]
            else:
                self.wait = True
                self.fixation_time = random.uniform(0.5, 4.0)

        return []

class AppearanceAnimator:
    def __init__(self, win):
        self.params = Global.live2d_animator.params
        self.win = win
        self.flag = 1
    
    def reset(self, k):
        self.k = k
        if self.k == 1:
            Global.exist = True
            self.win.show()
            self.interval = 1
        else:
            self._y = self.win.pos().y()
            self.interval = 2
        self.timer = Timer(self.interval)
        self.flag = 0
    
    def update(self):
        if self.flag == 0:
            t = self.timer.time() / self.interval
            if t <= 1:
                eased_t = sine(t)
                x = self.win.pos().x()
                if self.k == 1:
                    y = int(linearScale1(eased_t, 0, 1, self.win.screen_height, self._y))
                else:
                    y = int(linearScale1(eased_t, 0, 1, self._y, self.win.screen_height))
                self.win.move(x, y)
            else:
                if self.k != 1:
                    Global.exist = False
                    self.win.hide()
                self.flag = 1
        
        return []

class ExpressionAnimator:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.tasks = []

    def update(self):
        if self.tasks:
            result = []
            for i in range(len(self.tasks)-1, -1, -1):
                (param_id, param_max), timer, fadeout = self.tasks[i]
                fadeout /= 0.5
                t = (time.time() - timer) / 0.5
                if t <= 1:
                    result.append((param_id, linearScale1(t, 0, 1, 0, param_max), 1))
                elif 1 < t <= 1 + fadeout:
                    pass
                elif 1 + fadeout < t <= 2 + fadeout:
                    t -= fadeout
                    result.append((param_id, linearScale1(t, 1, 2, param_max, 0), 1))
                else:
                    result.append((param_id, 0, 1))
                    self.tasks.pop(i)

            return result

        return []
    
    def add(self, param, fadeout):
        self.tasks.append((param, time.time(), fadeout))

class EmotionAnimator:
    def __init__(self):
        self.params = Global.live2d_animator.params

        self.interval = 1
        self.flag = False
        self.flag1 = 0
    
    def update(self):
        if self.flag:
            t = self.timer.time() / self.interval
            if t > 1.0:
                self.flag = False
            else:
                eased_t = sine(t)
                if self.flag1 == 0:
                    self.flag1 += 1
                    self.s1 = self.params['ParamMouthForm']
                    self.s2 = self.params['ParamBrowLForm']
                    self.s3 = self.params['ParamBrowRForm']
                return [
                    ('ParamMouthForm', round(linearScale1(eased_t, 0, 1, self.s1, self.ParamMouthForm), 2), 1),
                    ('ParamBrowLForm', round(linearScale1(eased_t, 0, 1, self.s2, self.ParamBrowLForm), 2), 1),
                    ('ParamBrowRForm', round(linearScale1(eased_t, 0, 1, self.s3, self.ParamBrowRForm), 2), 1)
                ]

        return []
    
    def start(self, happy):
        self.ParamMouthForm = linearScale1(happy, 0, 10, -1, 1)
        self.ParamBrowLForm = linearScale1(happy, 0, 10, -1, 1)
        self.ParamBrowRForm = linearScale1(happy, 0, 10, -1, 1)

        self.timer = Timer(self.interval)
        self.flag = True
        self.flag1 = 0

class ExpMixAnimator:
    def __init__(self):
        self.flag = False
        self.timer = time.time()
        self.animators_sample = []

        self.mixanimator_wait_range = Global.character["Exp"]["mixanimator_wait_range"]
        self.wait = random.uniform(self.mixanimator_wait_range[0], self.mixanimator_wait_range[1])
        self.animators = {
            ExpAnimator1: ['ParamBrowLY', 'ParamBrowLAngle', 'ParamBrowRY', 'ParamBrowRAngle'],
            ExpAnimator3: ['ParamBrowLY', 'ParamBrowLAngle', 'ParamBrowRY', 'ParamBrowRAngle'],
            ExpAnimator4: ['ParamEyeLOpen', 'ParamEyeROpen'],
            ExpAnimator5: ['ParamEyeLOpen', 'ParamEyeROpen'],
            ExpAnimator6: ['ParamMouthX'],
        }

        weight_sum = sum(Global.character["Exp"]["mixanimator_weight"])
        self.p = [i / weight_sum for i in Global.character["Exp"]["mixanimator_weight"]]
        self.params = Global.live2d_animator.params
        for i in self.animators.values():
            for j in i:
                if j not in self.params:
                    self.params[j] = 0

        self.max_sample = Global.character["Exp"]["mixanimator_max_sample"]
        self.max_sample = min(len(self.animators), self.max_sample)
    
    def update(self):
        if self.flag:
            flag1 = False
            results = []
            for animator in self.animators_sample:
                result = animator.update()
                if not result is None:
                    flag1 = True
                    results += result
            
            if not flag1:
                self.flag = False
                self.timer = time.time()
                self.wait = random.uniform(self.mixanimator_wait_range[0], self.mixanimator_wait_range[1])
                Global.live2d_animator.blacklist1 = []

                return []
            return results

        elif time.time() - self.timer > self.wait:
            self.flag = True
            self.animators_sample = np.random.choice(
                list(self.animators.keys()), 
                size=random.randint(1, self.max_sample), 
                p=self.p, 
                replace=False
            ).tolist()

            related_params = set([])
            for i in range(len(self.animators_sample)-1, -1, -1):
                key = self.animators_sample[i]
                for param in self.animators[key]:
                    if param in related_params:
                        self.animators_sample.pop(i)
                        break
                    else:
                        related_params.add(param)
            
            for i in range(len(self.animators_sample)-1, -1, -1):
                key = self.animators_sample[i]
                for j in self.animators[key]:
                    a = False
                    if j in ['ParamEyeBallX', 'ParamEyeBallY']:
                        a = not Global.eyeball_animator.wait
                        if not a:
                            Global.live2d_animator.blacklist1.append('EyeBallAnimator')
                    elif j in ['ParamEyeLOpen', 'ParamEyeROpen']:
                        a = not Global.blink_animator.wait
                        if not a:
                            Global.live2d_animator.blacklist1.append('BlinkAnimator')

                    if a:
                        self.animators_sample.pop(i)
                        break
            
            self.animators_sample = [animator() for animator in self.animators_sample]
        
        return []

class BodyMixAnimator:
    def __init__(self):
        self.flag = False
        self.timer = time.time()
        self.animators_sample = []

        self.mixanimator_wait_range = Global.character["Body"]["mixanimator_wait_range"]
        self.wait = random.uniform(self.mixanimator_wait_range[0], self.mixanimator_wait_range[1])
        self.animators = {
            BodyAnimator1: ['ParamBodyAngleY', 'ParamAngleY', 'ParamEyeBallY'],
            BodyAnimator2: ['ParamAngleZ'],
            BodyAnimator3: ['ParamAngleX', 'ParamBodyAngleX'],
            BodyAnimator4: ['ParamAngleZ', 'ParamBodyAngleZ'],
            BodyAnimator5: ['OffsetX', 'OffsetY'],
            BodyAnimator6: ['Rotate'],
            BodyAnimator7: ['SetScale'],
            BodyAnimator8: ['OffsetX', 'OffsetY'],
        }

        weight_sum = sum(Global.character["Body"]["mixanimator_weight"])
        self.p = [i / weight_sum for i in Global.character["Body"]["mixanimator_weight"]]
        self.params = Global.live2d_animator.params
        for i in self.animators.values():
            for j in i:
                if j not in self.params:
                    self.params[j] = 0

        self.max_sample = Global.character["Body"]["mixanimator_max_sample"]
        self.max_sample = min(len(self.animators), self.max_sample)
    
    def update(self):
        if self.flag:
            flag1 = False
            results = []
            for animator in self.animators_sample:
                result = animator.update()
                if not result is None:
                    flag1 = True
                    results += result
            
            if not flag1:
                self.flag = False
                self.timer = time.time()
                self.wait = random.uniform(self.mixanimator_wait_range[0], self.mixanimator_wait_range[1])
                Global.live2d_animator.blacklist2 = []

                return []
            return results

        elif time.time() - self.timer > self.wait:
            self.flag = True
            self.animators_sample = np.random.choice(
                list(self.animators.keys()), 
                size=random.randint(1, self.max_sample), 
                p=self.p, 
                replace=False
            ).tolist()

            if Global.rvc and Global.rvc.playing:
                self.animators_sample[-1] = BodyAnimator6

            related_params = set([])
            for i in range(len(self.animators_sample)-1, -1, -1):
                key = self.animators_sample[i]
                for param in self.animators[key]:
                    if param in related_params:
                        self.animators_sample.pop(i)
                        break
                    else:
                        related_params.add(param)
            
            for i in range(len(self.animators_sample)-1, -1, -1):
                key = self.animators_sample[i]
                for j in self.animators[key]:
                    a = False
                    if j in ['ParamEyeBallX', 'ParamEyeBallY']:
                        a = not Global.eyeball_animator.wait
                        if not a:
                            Global.live2d_animator.blacklist2.append('EyeBallAnimator')
                    elif j in ['ParamEyeLOpen', 'ParamEyeROpen']:
                        a = not Global.blink_animator.wait
                        if not a:
                            Global.live2d_animator.blacklist2.append('BlinkAnimator')

                    if a:
                        self.animators_sample.pop(i)
                        break
            
            self.animators_sample = [animator() for animator in self.animators_sample]
        
        return []

class ExpAnimator1:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.interval = 1
        self.timer = Timer(self.interval)
        self.duration = random.uniform(0, 1)
        self.R_L = random.choice([-1, 1])
        self.flag1 = 0
        if self.R_L == 1:
            self.R = 'R'
            self.L = 'L'
        else:
            self.R = 'L'
            self.L = 'R'
    
    def update(self):
        t = self.timer.time() / self.interval
        if t <= 1:
            eased_t = cubic(t)
            if self.flag1 == 0:
                self.flag1 += 1
                self.s1 = self.params[f'ParamBrow{self.L}Y']
                self.s2 = self.params[f'ParamBrow{self.L}Angle']
                self.s3 = self.params[f'ParamBrow{self.R}Y']
                self.s4 = self.params[f'ParamBrow{self.R}Angle']
            return [
                (f'ParamBrow{self.L}Y', round(linearScale1(eased_t, 0, 1, self.s1, 1), 2), 1),
                (f'ParamBrow{self.L}Angle', round(linearScale1(eased_t, 0, 1, self.s2, -1), 2), 1),
                (f'ParamBrow{self.R}Y', round(linearScale1(eased_t, 0, 1, self.s3, 0), 2), 1),
                (f'ParamBrow{self.R}Angle', round(linearScale1(eased_t, 0, 1, self.s4, 0), 2), 1),
            ]
        elif t <= self.duration + 1:
            return []
        elif self.duration + 1 < t <= self.duration + 2:
            t -= self.duration + 1
            eased_t = cubic(t)
            if self.flag1 == 1:
                self.flag1 += 1
                self.s6 = self.params['ParamBrowLY']
                self.s7 = self.params['ParamBrowLAngle']
                self.s8 = self.params['ParamBrowRY']
                self.s9 = self.params['ParamBrowRAngle']
            return [
                ('ParamBrowLY', round(linearScale1(eased_t, 0, 1, self.s6, 0), 2), 1),
                ('ParamBrowLAngle', round(linearScale1(eased_t, 0, 1, self.s7, 0), 2), 1),
                ('ParamBrowRY', round(linearScale1(eased_t, 0, 1, self.s8, 0), 2), 1),
                ('ParamBrowRAngle', round(linearScale1(eased_t, 0, 1, self.s9, 0), 2), 1),
            ]
        else:
            return None

class ExpAnimator3:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.interval = 1
        self.timer = Timer(self.interval)
        self.duration = random.uniform(0, 1)
        self.BrowY = random.choice([-1, 0])
        self.flag1 = 0
    
    def update(self):
        t = self.timer.time() / self.interval
        if t <= 1:
            eased_t = cubic(t)
            if self.flag1 == 0:
                self.flag1 += 1
                self.s1 = self.params['ParamBrowLY']
                self.s2 = self.params['ParamBrowLAngle']
                self.s3 = self.params['ParamBrowRY']
                self.s4 = self.params['ParamBrowRAngle']
            return [
                ('ParamBrowLY', round(linearScale1(eased_t, 0, 1, self.s1, self.BrowY), 2), 1),
                ('ParamBrowLAngle', round(linearScale1(eased_t, 0, 1, self.s2, -1), 2), 1),
                ('ParamBrowRY', round(linearScale1(eased_t, 0, 1, self.s3, self.BrowY), 2), 1),
                ('ParamBrowRAngle', round(linearScale1(eased_t, 0, 1, self.s4, -1), 2), 1),
            ]
        elif t <= self.duration + 1:
            return []
        elif self.duration + 1 < t <= self.duration + 2:
            t -= self.duration + 1
            eased_t = cubic(t)
            if self.flag1 == 1:
                self.flag1 += 1
                self.s5 = self.params['ParamBrowLY']
                self.s6 = self.params['ParamBrowLAngle']
                self.s7 = self.params['ParamBrowRY']
                self.s8 = self.params['ParamBrowRAngle']
            return [
                ('ParamBrowLY', round(linearScale1(eased_t, 0, 1, self.s5, 0), 2), 1),
                ('ParamBrowLAngle', round(linearScale1(eased_t, 0, 1, self.s6, 0), 2), 1),
                ('ParamBrowRY', round(linearScale1(eased_t, 0, 1, self.s7, 0), 2), 1),
                ('ParamBrowRAngle', round(linearScale1(eased_t, 0, 1, self.s8, 0), 2), 1),
            ]
        else:
            return None

class ExpAnimator4:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.interval = 0.2
        self.timer = Timer(self.interval)
        self.duration = random.uniform(0, 1)
        self.k = random.choice([-1, 1])
        self.flag1 = 0
    
    def update(self):
        t = self.timer.time() / self.interval
        if t <= 1:
            eased_t = cubic(t)
            if self.flag1 == 0:
                self.flag1 += 1
                self.s1 = self.params['ParamEyeLOpen']
                self.s2 = self.params['ParamEyeROpen']
            return [
                ('ParamEyeLOpen', round(linearScale1(eased_t, 0, 1, self.s1, min(self.s1, max(0, self.k))), 2), 1),
                ('ParamEyeROpen', round(linearScale1(eased_t, 0, 1, self.s2, min(self.s2, max(0, self.k*-1))), 2), 1),
            ]
        elif t <= self.duration + 1:
            return []
        elif self.duration + 1 < t <= self.duration + 2:
            t -= self.duration + 1
            eased_t = cubic(t)
            if self.flag1 == 1:
                self.flag1 += 1
                self.s3 = self.params['ParamEyeLOpen']
                self.s4 = self.params['ParamEyeROpen']
            return [
                ('ParamEyeLOpen', round(linearScale1(eased_t, 0, 1, self.s3, self.s1), 2), 1),
                ('ParamEyeROpen', round(linearScale1(eased_t, 0, 1, self.s4, self.s2), 2), 1),
            ]
        else:
            return None

class ExpAnimator5:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.interval = 0.2
        self.timer = Timer(self.interval)
        if Global.rvc and Global.rvc.playing:
            self.duration = random.uniform(10, 20)
        else:
            self.duration = random.uniform(1, 3)
        self.flag1 = 0
    
    def update(self):
        t = self.timer.time() / self.interval
        if t <= 1:
            eased_t = cubic(t)
            if self.flag1 == 0:
                self.flag1 += 1
                self.s1 = self.params['ParamEyeLOpen']
                self.s2 = self.params['ParamEyeROpen']
            return [
                ('ParamEyeLOpen', round(linearScale1(eased_t, 0, 1, self.s1, 0), 2), 1),
                ('ParamEyeROpen', round(linearScale1(eased_t, 0, 1, self.s2, 0), 2), 1),
            ]
        elif t <= self.duration + 1:
            return []
        elif self.duration + 1 < t <= self.duration + 2:
            t -= self.duration + 1
            eased_t = cubic(t)
            if self.flag1 == 1:
                self.flag1 += 1
                self.s3 = self.params['ParamEyeLOpen']
                self.s4 = self.params['ParamEyeROpen']
            return [
                ('ParamEyeLOpen', round(linearScale1(eased_t, 0, 1, self.s3, self.s1), 2), 1),
                ('ParamEyeROpen', round(linearScale1(eased_t, 0, 1, self.s4, self.s2), 2), 1),
            ]
        else:
            return None

class ExpAnimator6:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.interval = 0.5
        self.timer = Timer(self.interval)
        self.duration = random.uniform(1, 3)
        self.k = random.choice([-1, 1])
        self.flag1 = 0
    
    def update(self):
        t = self.timer.time() / self.interval
        if t <= 1:
            eased_t = cubic(t)
            if self.flag1 == 0:
                self.flag1 += 1
                self.s1 = self.params['ParamMouthX']
            return [
                ('ParamMouthX', round(linearScale1(eased_t, 0, 1, self.s1, self.k*30), 2), 1),
            ]
        elif t <= self.duration + 1:
            return []
        elif self.duration + 1 < t <= self.duration + 2:
            t -= self.duration + 1
            eased_t = cubic(t)
            if self.flag1 == 1:
                self.flag1 += 1
                self.s2 = self.params['ParamMouthX']
            return [
                ('ParamMouthX', round(linearScale1(eased_t, 0, 1, self.s2, 0), 2), 1),
            ]
        else:
            return None

class BodyAnimator1:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.interval = random.uniform(0.8, 2)
        self.timer = Timer(self.interval)
        self.k = random.uniform(-1, 1)
        if random.random() > 0.5:
            self.k2 = random.random()
        else:
            self.k2 = -1
        self.flag1 = 0
    
    def update(self):
        t = self.timer.time() / self.interval
        if self.k2 == -1:
            if t <= 1:
                eased_t = sine(t)
                if self.flag1 == 0:
                    self.flag1 += 1
                    self.s1 = self.params['ParamBodyAngleY']
                    self.s2 = self.params['ParamAngleY']
                    self.s3 = self.params['ParamEyeBallY']
                return [
                    ('ParamBodyAngleY', round(linearScale1(eased_t, 0, 1, self.s1, 10*self.k), 2), 1),
                    ('ParamAngleY', round(linearScale1(eased_t, 0, 1, self.s2, 30*self.k), 2), 1),
                    ('ParamEyeBallY', round(linearScale1(eased_t, 0, 1, self.s3, -1*self.k), 2), 1),
                ]
            elif 1 < t <= 2:
                t -= 1
                eased_t = sine(t)
                if self.flag1 == 1:
                    self.flag1 += 1
                    self.s7 = self.params['ParamBodyAngleY']
                    self.s8 = self.params['ParamAngleY']
                    self.s9 = self.params['ParamEyeBallY']
                return [
                    ('ParamBodyAngleY', round(linearScale1(eased_t, 0, 1, self.s7, 0), 2), 1),
                    ('ParamAngleY', round(linearScale1(eased_t, 0, 1, self.s8, 0), 2), 1),
                    ('ParamEyeBallY', round(linearScale1(eased_t, 0, 1, self.s9, 0), 2), 1),
                ]
            else:
                return None
        else:
            if t <= 1:
                eased_t = sine(t)
                if self.flag1 == 0:
                    self.flag1 += 1
                    self.s1 = self.params['ParamBodyAngleY']
                    self.s2 = self.params['ParamAngleY']
                    self.s3 = self.params['ParamEyeBallY']
                return [
                    ('ParamBodyAngleY', round(linearScale1(eased_t, 0, 1, self.s1, 10*self.k), 2), 1),
                    ('ParamAngleY', round(linearScale1(eased_t, 0, 1, self.s2, 30*self.k), 2), 1),
                    ('ParamEyeBallY', round(linearScale1(eased_t, 0, 1, self.s3, -1*self.k), 2), 1),
                ]
            elif 1 < t <= 2:
                t -= 1
                eased_t = sine(t)
                if self.flag1 == 1:
                    self.flag1 += 1
                    self.s4 = self.params['ParamBodyAngleY']
                    self.s5 = self.params['ParamAngleY']
                    self.s6 = self.params['ParamEyeBallY']
                return [
                    ('ParamBodyAngleY', round(linearScale1(eased_t, 0, 1, self.s4, -10*self.k*self.k2), 2), 1),
                    ('ParamAngleY', round(linearScale1(eased_t, 0, 1, self.s5, -30*self.k*self.k2), 2), 1),
                    ('ParamEyeBallY', round(linearScale1(eased_t, 0, 1, self.s6, 1*self.k*self.k2), 2), 1),
                ]
            elif 2 < t <= 3:
                t -= 2
                eased_t = sine(t)
                if self.flag1 == 2:
                    self.flag1 += 1
                    self.s7 = self.params['ParamBodyAngleY']
                    self.s8 = self.params['ParamAngleY']
                    self.s9 = self.params['ParamEyeBallY']
                return [
                    ('ParamBodyAngleY', round(linearScale1(eased_t, 0, 1, self.s7, 0), 2), 1),
                    ('ParamAngleY', round(linearScale1(eased_t, 0, 1, self.s8, 0), 2), 1),
                    ('ParamEyeBallY', round(linearScale1(eased_t, 0, 1, self.s9, 0), 2), 1),
                ]
            else:
                return None

class BodyAnimator2:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.interval = random.uniform(0.8, 1)
        self.timer = Timer(self.interval)
        self.k = random.uniform(-0.4, 0.4)
        self.flag1 = 0
        self.easing_functions = [
            cubic,
            quart,
            sine
        ]
        self.current_easing = random.choice(self.easing_functions)
    
    def update(self):
        t = self.timer.time() / self.interval
        if t <= 1:
            eased_t = self.current_easing(t)
            if self.flag1 == 0:
                self.flag1 += 1
                self.s1 = self.params['ParamAngleZ']
            return [
                ('ParamAngleZ', round(linearScale1(eased_t, 0, 1, self.s1, 30*self.k), 2), 1),
            ]
        else:
            return None

class BodyAnimator3:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.interval = random.uniform(0.8, 2)
        self.timer = Timer(self.interval)
        self.k = random.uniform(-0.5, 0.5)
        self.flag1 = 0
        self.easing_functions = [
            cubic,
            quart,
            sine
        ]
        self.current_easing = random.choice(self.easing_functions)
    
    def update(self):
        t = self.timer.time() / self.interval
        if t <= 1:
            eased_t = self.current_easing(t)
            if self.flag1 == 0:
                self.flag1 += 1
                self.s1 = self.params['ParamAngleX']
                self.s2 = self.params['ParamBodyAngleX']
            return [
                ('ParamAngleX', round(linearScale1(eased_t, 0, 1, self.s1, 30*self.k), 2), 1),
                ('ParamBodyAngleX', round(linearScale1(eased_t, 0, 1, self.s2, 10*self.k), 2), 1),
            ]
        else:
            return None

class BodyAnimator4:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.interval = random.uniform(0.8, 1)
        self.timer = Timer(self.interval)
        self.k = random.uniform(-0.4, 0.4)
        self.flag1 = 0
        self.easing_functions = [
            cubic,
            quart,
            sine
        ]
        self.current_easing = random.choice(self.easing_functions)
    
    def update(self):
        t = self.timer.time() / self.interval
        if t <= 1:
            eased_t = self.current_easing(t)
            if self.flag1 == 0:
                self.flag1 += 1
                self.s1 = self.params['ParamAngleZ']
                self.s2 = self.params['ParamBodyAngleZ']
            return [
                ('ParamAngleZ', round(linearScale1(eased_t, 0, 1, self.s1, 30*self.k), 2), 1),
                ('ParamBodyAngleZ', round(linearScale1(eased_t, 0, 1, self.s2, 10*self.k), 2), 1),
            ]
        else:
            return None

class BodyAnimator5:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.model = Global.model
        self.interval = random.uniform(0.5, 1)
        self.flag1 = 0
        self.timer = Timer(self.interval)
        self.k = random.uniform(-0.08, 0.08)
        self.easing_functions = [
            cubic,
            quart,
            sine
        ]
        self.current_easing = random.choice(self.easing_functions)
    
    def update(self):
        t = self.timer.time() / self.interval
        if t <= 1:
            eased_t = self.current_easing(t)
            if self.flag1 == 0:
                self.flag1 += 1
                self.s1 = self.params['OffsetY']
            y = linearScale1(eased_t, 0, 1, self.s1, self.k)
            self.model.SetOffset(0, y)
            self.params['OffsetY'] = y

            return []
        else:
            return None
        
class BodyAnimator6:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.model = Global.model
        self.num = random.randint(1, 3)
        self.k = random.choice([-1, 1])
        self.count = 0
        self.reset()
    
    def reset(self):
        self.interval = random.uniform(0.5, 1)
        self.flag1 = 0
        self.timer = Timer(self.interval)
        if self.k > 0:
            self.k = random.uniform(2, 10)*-1
        else:
            self.k = random.uniform(2, 10)
        self.easing_functions = [
            cubic,
            quart,
            sine
        ]
        self.current_easing = random.choice(self.easing_functions)
    
    def update(self):
        t = self.timer.time() / self.interval
        if t <= 1:
            eased_t = self.current_easing(t)
            if self.flag1 == 0:
                self.flag1 += 1
                self.s1 = self.params['Rotate']
            y = linearScale1(eased_t, 0, 1, self.s1, self.k)
            self.model.Rotate(y)
            self.params['Rotate'] = y

        else:
            if self.count == self.num+1:
                return None
            if self.count != self.num:
                self.count += 1
                self.reset()
            else:
                self.count += 1
                self.reset()
                self.k = 0
        
        return []

class BodyAnimator7:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.model = Global.model
        self.interval = random.uniform(0.5, 1)
        self.flag1 = 0
        self.timer = Timer(self.interval)
        self.k = random.uniform(1, 1.1)
        self.easing_functions = [
            cubic,
            quart,
            sine
        ]
        self.current_easing = random.choice(self.easing_functions)
    
    def update(self):
        t = self.timer.time() / self.interval
        if t <= 1:
            eased_t = self.current_easing(t)
            if self.flag1 == 0:
                self.flag1 += 1
                if self.params['SetScale'] == 0:
                    self.params['SetScale'] = 1
                self.s1 = self.params['SetScale']

            y = linearScale1(eased_t, 0, 1, self.s1, self.k)
            self.model.SetScale(y)
            self.params['SetScale'] = y

            return []
        else:
            return None

class BodyAnimator8:
    def __init__(self):
        self.params = Global.live2d_animator.params
        self.model = Global.model
        self.num = random.randint(1, 3)
        self.k = random.choice([-1, 1])
        self.count = 0
        self.reset()
    
    def reset(self):
        self.interval = random.uniform(0.3, 0.6)
        self.flag1 = 0
        self.timer = Timer(self.interval)
        if self.k > 0:
            self.k = random.uniform(0, 0.06)*-1
        else:
            self.k = random.uniform(0, 0.06)
        self.easing_functions = [
            cubic,
            quart,
            sine
        ]
        self.current_easing = random.choice(self.easing_functions)
    
    def update(self):
        t = self.timer.time() / self.interval
        if t <= 1:
            eased_t = self.current_easing(t)
            if self.flag1 == 0:
                self.flag1 += 1
                self.s1 = self.params['OffsetY']
            y = linearScale1(eased_t, 0, 1, self.s1, self.k)
            self.model.SetOffset(0, y)
            self.params['OffsetY'] = y

        else:
            if self.count == self.num+1:
                return None
            if self.count != self.num:
                self.count += 1
                self.reset()
            else:
                self.count += 1
                self.reset()
                self.k = 0
        
        return []