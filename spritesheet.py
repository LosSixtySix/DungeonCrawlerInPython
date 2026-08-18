import pygame

class spriteSheet:
    def __init__(self,filename):
        self.filename = filename
        self.sprite_sheet = pygame.image.load(filename).convert_alpha()
        # self.spriteCounter = 0
    def get_sprite(self,x,y,w,h):
        sprite = pygame.Surface((w,h),pygame.SRCALPHA)
        sprite.fill((0,0,0,0))
        sprite.blit(self.sprite_sheet,(0,0),(x,y,w,h))
        # pygame.image.save(sprite,f"sprite{self.spriteCounter}.png")
        # self.spriteCounter += 1
        return sprite