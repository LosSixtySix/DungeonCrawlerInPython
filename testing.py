import pygame


pygame.init()
black = [0,0,0]
win = pygame.display.set_mode((720,720))

while True:
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                print("Clicked")
    
    
    #KEYS = pygame.key.get_pressed()
        
    #if KEYS[pygame.K_RETURN]:
    #    print("clicked")

    win.fill((black))